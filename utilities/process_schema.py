#!/usr/bin/env python
import argparse
import os
import pickle
import re
import sys
from collections import Counter
from collections import namedtuple
from datetime import datetime
from textwrap import TextWrapper
from typing import TextIO

import xmlschema
from markdownTable import markdownTable
from toposort import toposort_flatten

AttributeInfo = namedtuple("AttributeInfo", ("name", "type", "description"))


def camel_to_snake(name):
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def process_element_type(element, phash, abstract_class_list, prefix):
    type = element.type
    is_complex = type.is_complex()
    phash["is_complex"] = is_complex
    phash["is_abstract"] = False
    thistype = "str"
    if is_complex:
        if type.name is not None:
            name = element.type.name.strip()
            phash["is_abstract"] = name in abstract_class_list
            if name == "{C}OCITable":
                thistype = "list"
                phash["is_table"] = True
            elif name.startswith("{"):
                phash["unknown"] = True  # TODO more complex type handling
            else:
                thistype = prefix + name
        else:
            phash["is_container"] = True
            phash["contents"] = build_element_hash(
                element.type,
                abstract_class_list,
                prefix,
            )
    else:
        if type.primitive_type.id == "boolean":
            thistype = "bool"
        elif type.primitive_type.id == "decimal":
            thistype = "int"
    phash["type"] = thistype


def build_element_hash(xsd_component, abstract_class_list, prefix=""):
    element_hash = {}
    for elem in xsd_component.content.iter_elements():
        name = camel_to_snake(elem.name.strip())
        is_required = True if elem.min_occurs > 0 else False
        if is_required:
            if elem.parent.model == "choice":
                is_required = False
            elif elem.parent.model == "sequence":
                gparent = elem.parent.parent
                if hasattr(gparent, "model") and gparent.model == "choice":
                    is_required = False
        if elem.min_occurs is None:
            if elem.max_occurs is None:
                is_array = False
            elif elem.max_occurs == 1:
                is_array = False
            else:
                is_array = True
        elif elem.min_occurs <= 1 and elem.max_occurs == 1:
            is_array = False
        else:
            is_array = True
        phash = {
            "name": name,
            "xmlname": elem.name.strip(),
            "is_required": is_required,
            "is_array": is_array,
            "is_table": False,
            "is_container": False,
            "unknown": False,
        }
        process_element_type(elem, phash, abstract_class_list, prefix)
        element_hash[name] = phash
    return element_hash


def write_elements(file, elements):
    """Write the _Elements array used for serializing to/from XML"""
    file.write("    @classmethod\n")
    file.write("    def _elements(cls) -> Tuple[E, ...]:\n")
    if len(elements):
        # We have elements - write them out - starting with the header
        file.write("        return (\n")
        for element in elements.values():
            outstr = write_element(element)
            file.write(f"            {outstr}\n")
        file.write("        )\n")
    else:
        # No elements - we write an empty set out
        file.write("        return ()\n")


def write_element(element) -> str:
    outstr = f'E("{element["name"]}", "{element["xmlname"]}", '
    if element["is_container"]:
        contents = []
        for subelement in element["contents"].values():
            contents.append(write_element(subelement))
        outstr += f"[{' '.join(contents)}],"
    else:
        outstr += f"{element['type']},"
    for query in (
        "is_complex",
        "is_required",
        "is_array",
        "is_table",
        "is_abstract",
        "is_container",
    ):
        if element[query]:
            outstr += f" {query}=True,"
    comment = "  # unknown" if element["unknown"] else ""
    outstr += f"),{comment}"
    return outstr


def write_slots(file, elements, thing):
    file.write("    __slots__: List[str] = [\n")
    for element in elements.values():
        file.write(f'        "{element["name"]}",\n')
    file.write("    ]\n\n")


def process_class_elements(file, elements, thing):
    write_slots(file, elements, thing)
    write_elements(file, elements)


def make_attribute_info(prefix, elements):
    info = []
    for element in elements.values():
        if element["is_table"]:
            type = f"List({element['xmlname']})"
            suffix = f" - *Table* array of {element['xmlname']} named tuples"
        else:
            suffix = ""
            if element["is_complex"]:
                type = prefix + element["xmlname"]
            else:
                type = element["type"]
            if element["is_array"]:
                type = f"List[{type}]"
        if not element["is_required"]:
            suffix += " *Optional*"
        info.append(
            AttributeInfo(element["name"], type, f"{element['xmlname']}{suffix}"),
        )
    return info


def make_documentation_block(xsd_component):
    lines = []
    anno = xsd_component.annotation
    if anno:
        wrapper = TextWrapper(
            width=86,
            initial_indent="",
            subsequent_indent="",
            break_long_words=False,
            drop_whitespace=True,
            fix_sentence_endings=True,
            expand_tabs=False,
        )
        for doc in anno.documentation:
            # text with leading/trailing spaces stripped
            text = doc.text.strip()
            # text with internal spacing collapsed
            text = re.sub(r"\s+", " ", text)
            # mark up magic method markers
            text = re.sub(
                r"\b([A-Z][A-Za-z0-9]*(?:Request|Response)(?:\d+(?:(?:mp|sp|V)\d+)?)?)\b",
                r"`\1()`",
                text,
            )
            # Fix a standard oddity
            text = re.sub(r"^Replaced [Bb]y:", r"Replaced By", text)
            # weird escaped sequence in docs that breaks python
            text = re.sub(r"\\\s", r" ", text)
            # break off first sentence
            segments = text.split(".", 1)
            text = segments.pop().lstrip()
            if len(segments) > 0:
                segments[0] += "."  # put the full stop back
            # break off response part if present
            pos = text.find("The response")
            if pos > 0:
                segments.append(text[:pos].rstrip())
                text = text[pos:]
            # break off Replaced By
            pos = text.find("Replaced By")
            if pos > 0:
                segments.append(text[:pos].rstrip())
                segments.append(text[pos:])
            else:
                segments.append(text)
            for mystr in segments:
                if len(lines) > 0:
                    lines.append("")
                lines += wrapper.wrap(mystr)
    return lines


def process_markdown_documentation(
    file,
    class_name,
    base_class,
    doc_lines,
    attribute_info,
):
    file.write("\n")
    file.write(
        f"## `{class_name}`([`{base_class}`](/broadworks_ocip/api/base/#broadworks_ocip.base.{base_class}))\n",
    )
    file.write("\n")
    file.write('<div class="doc-contents" markdown="1">\n')
    file.write("\n".join(doc_lines))
    file.write("\n")
    if len(attribute_info) > 0:
        file.write("\n")
        file.write("**Attributes:**\n\n")
        file.write(
            markdownTable(
                [
                    {
                        "Name": attr.name,
                        "Type": attr.type,
                        "Description": attr.description,
                    }
                    for attr in attribute_info
                ],
            )
            .setParams(
                row_sep="markdown",
                quote=False,
                padding_width=1,
                padding_weight="right",
            )
            .getMarkdown(),
        )
    file.write("\n")
    file.write("</div>\n")
    file.write("\n")


def process_class_documentation(file, doc_lines, attribute_info):
    if len(doc_lines) + len(attribute_info) == 0:
        return

    file.write('    """\n')
    for line in doc_lines:
        if len(line) > 0:
            file.write(f"    {line}\n")
        else:
            file.write("\n")
    if len(attribute_info) > 0:
        file.write("\n")
        file.write("    Attributes:\n")
        wrapper = TextWrapper(
            width=90,
            initial_indent=" " * 8,
            subsequent_indent=" " * 12,
            break_long_words=False,
            drop_whitespace=True,
            fix_sentence_endings=True,
            expand_tabs=False,
        )
        for attr in attribute_info:
            file.write(
                "\n".join(
                    wrapper.wrap(f"{attr.name} ({attr.type}): {attr.description}"),
                ),
            )
            file.write("\n")
    file.write('    """\n\n')


def process_thing(file, doc_file, xsd_component, abstract_class_list, thing, prefix=""):
    base = thing
    if xsd_component.is_extension() and not xsd_component.base_type.name.startswith(
        "{C}",
    ):
        base = prefix + xsd_component.base_type.name
    file.write(f"class {xsd_component.name}({base}):\n")
    elements = build_element_hash(xsd_component, abstract_class_list, prefix)
    attribute_info = make_attribute_info(prefix, elements)
    doc_lines = make_documentation_block(xsd_component)
    process_class_documentation(file, doc_lines, attribute_info)
    process_class_elements(file, elements, thing)
    file.write("\n\n")
    process_markdown_documentation(
        doc_file,
        xsd_component.name,
        thing,
        doc_lines,
        attribute_info,
    )


def process_request(file, doc_file, xsd_component, abstract_class_list):
    process_thing(
        file,
        doc_file,
        xsd_component,
        abstract_class_list,
        "OCIRequest",
        "OCI.",
    )


def process_response(file, doc_file, xsd_component, abstract_class_list):
    process_thing(
        file,
        doc_file,
        xsd_component,
        abstract_class_list,
        "OCIResponse",
        "OCI.",
    )


def process_type(file, doc_file, xsd_component, abstract_class_list):
    process_thing(file, doc_file, xsd_component, abstract_class_list, "OCIType", "")


def process_schema(
    schema,
    class_list,
    abstract_class_list,
    types_file,
    requests_file,
    responses_file,
    types_docfile,
    requests_docfile,
    responses_docfile,
):
    for item in class_list:
        xsd_component = schema.types[item]
        if xsd_component.is_complex():
            match = re.search(
                # Look for Requests/Responses but exclude SearchCriteria
                r"^(?!SearchCriteria).+(Request|Response)(\d+((mp|sp|V)\d+)?)?$",
                xsd_component.name,
            )
            if match and match.group(1) == "Request":
                process_request(
                    requests_file,
                    requests_docfile,
                    xsd_component,
                    abstract_class_list,
                )
            elif match and match.group(1) == "Response":
                process_response(
                    responses_file,
                    responses_docfile,
                    xsd_component,
                    abstract_class_list,
                )
            else:
                process_type(
                    types_file,
                    types_docfile,
                    xsd_component,
                    abstract_class_list,
                )


def sort_schema(schema):
    dependancy_map = {}
    for xsd_component in schema.iter_globals():
        if xsd_component.is_complex():
            name = xsd_component.name
            dependancies = Counter()
            # look for our base classes
            if xsd_component.is_extension():
                if not xsd_component.base_type.name.startswith("{C}"):
                    dependancies[xsd_component.base_type.name] += 1
            # find components that we use
            for elem in xsd_component.content.iter_elements():
                type = elem.type
                if type.is_complex() and type.name is not None:
                    if re.search(r"^[A-Za-z0-9]+$", type.name):
                        dependancies[type.name] += 1
            dependancy_map[name] = set(dependancies.keys())
    return toposort_flatten(dependancy_map, sort=True)


def build_abstract_class_list(schema):
    """Creates a list of all OCI classes that are marked as abstract"""
    abstract_class_list = []
    for xsd_component in schema.iter_globals():
        if xsd_component.is_complex() and xsd_component.abstract:
            abstract_class_list.append(xsd_component.name)
    return abstract_class_list


def open_output_files(prevent_reformat: bool):
    results = []
    generation_time = datetime.now()
    for thing in ("type", "request", "response"):
        filename = os.path.join("broadworks_ocip", thing + "s.py")
        out = open(filename, "w")
        out.write(f'"""Broadworks OCI-P Interface {thing.title()} Classes"""\n')
        out.write("# Autogenerated from the Broadworks XML Schemas.\n")
        out.write("# Do not edit as changes will be overwritten.\n")
        out.write(f"# Generated on {generation_time.isoformat()}\n")
        if prevent_reformat:
            out.write("# fmt: off\n")
        out.write("from typing import List\n")
        out.write("from typing import Tuple\n\n")
        if thing in ("request", "response"):
            out.write("import broadworks_ocip.types as OCI\n")
        out.write("from .base import ElementInfo as E\n")
        out.write(f"from .base import OCI{thing.title()}\n")
        out.write("\n\n")
        results.append(out)
    return results[0], results[1], results[2]


def open_doc_files():
    results = []
    generation_time = datetime.now()
    for thing in ("type", "request", "response"):
        filename = os.path.join("docs/api", thing + "s.md")
        out = open(filename, "w")
        out.write("<!--\n")
        out.write("# Autogenerated from Broadworks XML Schemas\n")
        out.write("# Do not edit as changes will be overwritten.\n")
        out.write(f"# Generated on {generation_time.isoformat()}\n")
        out.write("-->\n")
        out.write(f"# {thing.title()}s\n")
        out.write("\n")
        results.append(out)
    return results[0], results[1], results[2]


def close_output_files(
    prevent_reformat: bool,
    types_file: TextIO,
    requests_file: TextIO,
    responses_file: TextIO,
):
    for out in (types_file, requests_file, responses_file):
        if prevent_reformat:
            out.write("# fmt: on\n")
        out.write("# end\n")


def main():
    parser = argparse.ArgumentParser(
        description="Parse Broadworks OCI-P schema, build interface code",
    )
    parser.add_argument(
        "--schema",
        type=str,
    )
    parser.add_argument(
        "--unpickle",
        action="store_true",
    )
    parser.add_argument(
        "--pickle",
        action="store_true",
    )
    parser.add_argument(
        "--block-black",
        action="store_true",
    )
    args = parser.parse_args()
    if args.schema:
        schema = xmlschema.XMLSchema(args.schema)
        print("Loaded schema")
        if args.pickle:
            file = open("schema.pkl", "wb")
            pickle.dump(schema, file, protocol=pickle.HIGHEST_PROTOCOL)
    else:
        if args.unpickle:
            file = open("schema.pkl", "rb")
            schema = pickle.load(file)
            print("Unpickled schema")
        else:
            sys.exit("No schema")
    class_list = sort_schema(schema)
    print("Sorted schema")
    abstract_class_list = build_abstract_class_list(schema)
    types_file, requests_file, responses_file = open_output_files(args.block_black)
    types_docfile, requests_docfile, responses_docfile = open_doc_files()
    process_schema(
        schema,
        class_list,
        abstract_class_list,
        types_file,
        requests_file,
        responses_file,
        types_docfile,
        requests_docfile,
        responses_docfile,
    )
    close_output_files(args.block_black, types_file, requests_file, responses_file)


if __name__ == "__main__":
    main()
