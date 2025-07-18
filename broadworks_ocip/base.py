"""
Broadworks OCI-P Interface Base Classes

Base classes used by the types, requests and responses as well as
other components like ElementInfo that are used by those.
"""

import logging
import re
from collections import namedtuple
from typing import Any
from typing import Dict
from typing import List
from typing import NamedTuple
from typing import Tuple

import attr
from lxml import etree
from null_object import Null

from broadworks_ocip.exceptions import OCIErrorAPISetup
from broadworks_ocip.exceptions import OCIErrorAttributeMissing
from broadworks_ocip.exceptions import OCIErrorResponse
from broadworks_ocip.exceptions import OCIErrorUnexpectedAttribute


logger = logging.getLogger(__name__)

# constants
XML_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"
XSD_INST = "http://www.w3.org/2001/XMLSchema-instance"
XSD_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"


@attr.s(slots=True, frozen=True)
class ElementInfo:
    """
    ElementInfo - information on each element of a Broadsoft OCIType

    Used to describe the element when serialising to/from XML

    Attributes:
        name: name of this element (in python snake case)
        xmlname: name of this element (in Java like camel case)
        type: the type of the resulting element
        is_complex: is this a complex element - containing another OCIType derived class
        is_required: Is this required (True) or Optional (False)
        is_array: Is this an array/list of element values
        is_table: Is this a Broadworks table type - only seen in Responses
    """

    name: str = attr.ib()
    xmlname: str = attr.ib()
    type = attr.ib()
    is_complex: bool = attr.ib(default=False)
    is_required: bool = attr.ib(default=False)
    is_array: bool = attr.ib(default=False)
    is_table: bool = attr.ib(default=False)
    is_abstract: bool = attr.ib(default=False)
    is_container: bool = attr.ib(default=False)


class OCIType:
    """
    OCIType - Base type for all the OCI-P component classes

    There are no attributes of this base class (the `_frozen` attribute is
    used as a flag to lock the instance).  The attributes are added in the
    various subclasses.
    """

    __slots__: List[str] = ["_frozen"]

    def __init__(self, **kwargs):
        cname = type(self).__name__  # needed for error messages
        for elem in self._elements():
            if elem.name in kwargs:
                value = kwargs[elem.name]
                if elem.is_required and value is None:
                    raise OCIErrorAttributeMissing(
                        message=f"{cname}: Required attribute {elem.name} is missing",
                    )
                if value is Null:
                    # always allowed
                    pass
                elif elem.is_array:
                    if not isinstance(value, list):
                        raise TypeError(
                            f"{cname}: Expected {elem.name} to be a list but it is {type(value)}",
                        )
                    if len(value) > 0 and not isinstance(value[0], elem.type):
                        raise TypeError(
                            f"{cname}: Expected first element of {elem.name} to be type {elem.type} but it is {type(value[0])}",
                        )
                elif elem.is_table:
                    if not isinstance(value, list):
                        raise TypeError(
                            f"{cname}: Expected {elem.name} to be a table/list but it is {type(value)}",
                        )
                elif elem.is_container:
                    if value is not None and not isinstance(value, dict):
                        raise TypeError(
                            f"{cname}: Expected {elem.name} to be a dict of elements but it is {type(value)}",
                        )
                elif not isinstance(value, elem.type):
                    raise TypeError(
                        f"{cname}: Expected {elem.name} to be type {elem.type} but it is {type(value)}",
                    )
                setattr(self, elem.name, value)
                del kwargs[elem.name]
            elif elem.is_required:
                raise OCIErrorAttributeMissing(
                    message=f"{cname}: Required attribute {elem.name} is missing",
                )
            else:
                setattr(self, elem.name, None)
        if kwargs:
            raise OCIErrorUnexpectedAttribute(
                message=f"{cname}: Unexpected attribute(s) {kwargs.keys()}",
            )
        self._frozen = True

    def __delattr__(self, *args, **kwargs):
        if hasattr(self, "_frozen"):
            raise AttributeError("This object is frozen!")
        object.__delattr__(self, *args, **kwargs)

    def __setattr__(self, *args, **kwargs):
        if hasattr(self, "_frozen"):
            raise AttributeError("This object is frozen!")
        object.__setattr__(self, *args, **kwargs)

    # Namespace maps used for various XML build tasks
    @classmethod
    def _default_nsmap(cls):
        return {None: "", "xsi": "http://www.w3.org/2001/XMLSchema-instance"}

    @classmethod
    def _document_nsmap(cls):
        return {None: "C", "xsi": "http://www.w3.org/2001/XMLSchema-instance"}

    @classmethod
    def _error_nsmap(cls):
        return {
            "c": "C",
            None: "",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        }

    @classmethod
    def _elements(cls) -> Tuple[ElementInfo, ...]:
        raise OCIErrorAPISetup(message="_elements should be defined in the subclass.")

    @property
    def type_(self):
        """Return the typename of the class"""
        return self.__class__.__name__

    @classmethod
    def class_to_property_(self, name):
        """Map a XML class name to the associated property"""
        return name[0].lower() + name[1:]

    def post_xml_decode_(self):
        """
        Carry out any operations after the XML decode

        Intended for use by subclasses where they need to take actions immediately
        after they are created from an incoming XML document.
        """
        pass

    def etree_components_(self, name=None):
        """
        Build XML etree element tree for this OCIType

        Arguments:
            name: The name or tag of the element - defaults to the `type_`

        Returns:
            etree: etree.Element() for this class
        """
        if name is None:
            name = self.type_
        element = etree.Element(name, nsmap=self._default_nsmap())
        return self.etree_sub_components_(element)

    def etree_sub_components_(self, element: etree._Element) -> etree._Element:
        """
        Build XML etree subelements for the components within this OCIType

        Arguments:
            element: The parent element that the components are to be attached to

        Returns:
            etree: etree.Element() for this class
        """
        for sub_element in self._elements():
            value = getattr(self, sub_element.name)
            if sub_element.is_array:
                if value is not None:
                    if len(value) == 0:
                        element.attrib[XML_NIL] = "true"
                    else:
                        for subvalue in value:
                            self.etree_sub_element_(element, sub_element, subvalue)
            else:
                self.etree_sub_element_(element, sub_element, value)
        return element

    def etree_sub_element_(
        self,
        element: etree._Element,
        sub_element: ElementInfo,
        value,
    ) -> etree._Element:
        """
        Build XML etree subelement for one element within this OCIType

        Arguments:
            element: The parent element that the components are to be attached to
            sub_element: The definition of the sub element to be attached
            value: Value of the sub element - quite possibly None

        Returns:
            etree: etree.Element() for this class
        """
        # if value is Null or (value is None and sub_element.is_required):
        if value is Null or (value is None and sub_element.is_required):
            etree.SubElement(
                element,
                sub_element.xmlname,
                {XML_NIL: "true"},
                nsmap=self._default_nsmap(),
            )
        elif value is None:
            pass
        elif sub_element.is_table:
            # any table should be a list of namedtuple elements
            if isinstance(value, list) and len(value) > 0:
                elem = etree.SubElement(
                    element,
                    sub_element.xmlname,
                    nsmap=self._default_nsmap(),
                )
                first = value[0]
                for col in first._fields:
                    col_heading = etree.SubElement(elem, "colHeading")
                    col_heading.text = self.snake_case_to_column_header(col)
                for row in value:
                    row_item = etree.SubElement(elem, "row")
                    for col in row:
                        col_item = etree.SubElement(row_item, "col")
                        col_item.text = col
        elif sub_element.is_container:
            elem = etree.SubElement(
                element,
                sub_element.xmlname,
                nsmap=self._default_nsmap(),
            )
            for item in sub_element.type:
                if item.name in value:
                    self.etree_sub_element_(elem, item, value[item.name])
        elif sub_element.is_complex:
            if sub_element.is_abstract:
                elem = etree.SubElement(
                    element,
                    sub_element.xmlname,
                    {XSD_TYPE: value.type_},
                    nsmap=self._default_nsmap(),
                )
            else:
                elem = etree.SubElement(
                    element,
                    sub_element.xmlname,
                    nsmap=self._default_nsmap(),
                )
            value.etree_sub_components_(elem)
        else:
            elem = etree.SubElement(
                element,
                sub_element.xmlname,
                nsmap=self._default_nsmap(),
            )
            if sub_element.type is bool:
                elem.text = "true" if value else "false"
            elif sub_element.type is int:
                elem.text = str(value)
            else:
                elem.text = value
        return element

    @classmethod
    def column_header_snake_case_(cls, header: str) -> str:
        """
        Converts an XML name into a pythonic snake case name

        Arguments:
            header: The header name in space separated words

        Returns:
            snake: lower cased and underscore separated result name
        """
        return re.sub("[^A-Za-z0-9]+", r"_", header).lower()

    def snake_case_to_column_header(self, snake_str: str) -> str:
        """
        Converts a pythonic snake case name into a column header name

        Arguments:
            snake_str: The header name in snake lower case

        Returns:
            column_header: initial capital and space separated result name
        """
        components = snake_str.split("_")
        # We capitalize the first letter of each component except the first one
        # with the 'title' method and join them together.
        return " ".join(x.title() for x in components)

    @classmethod
    def decode_table_(cls, element: etree._Element) -> List[NamedTuple]:
        """
        Decode a table (used in a OCIResponse) into a list of named tuples

        Arguments:
            element: The OCITable XML element

        Returns:
            results: List of namedtuple elements, one for each table row
        """
        typename: str = element.tag
        results: List[NamedTuple] = []
        columns = [cls.column_header_snake_case_(b.text) for b in element.iterfind("colHeading")]
        type: NamedTuple = namedtuple(typename, columns)  # type: ignore
        for row in element.iterfind("row"):
            rowdata = [b.text for b in row.iterfind("col")]
            rowobj = type(*rowdata)
            results.append(rowobj)
        return results

    @classmethod
    def build_from_etree_non_parameters_(
        cls,
        element: etree._Element,
        initialiser: dict,
    ) -> None:
        """
        Handle any items outside the parameter set

        Intended for use by subclasses where they need to take actions immediately
        after they are created from an incoming XML document.
        """
        pass

    @classmethod
    def build_from_node_(
        cls,
        api: "BroadworksAPI",  # type: ignore # noqa
        elem: ElementInfo,
        node: etree._Element,
    ) -> Any:
        """
        Creates an OCI subelement from a single  XML etree node

        Arguments:
            elem: The subelement descriptor
            node: The OCITable XML element node

        Returns:
            results: Object instance for this class
        """
        if node is not None:
            if XML_NIL in node.attrib and node.attrib[XML_NIL] == "true":
                return Null
            elif elem.is_table:
                return cls.decode_table_(node)
            elif elem.is_complex:
                if elem.is_abstract:
                    if XSD_TYPE in node.attrib:
                        thisclass = api.get_type_class(
                            node.attrib[XSD_TYPE],
                        )
                        logger.error(f"thisclass={thisclass}")
                        return thisclass.build_from_etree_(api=api, element=node)
                    else:
                        return ValueError("Cannot decode abstract object")
                elif elem.is_container:
                    return cls.build_initialiser_from_etree_(
                        api=api,
                        element=node,
                        subelement_set=elem.type,
                    )
                else:
                    return elem.type.build_from_etree_(api=api, element=node)
            elif elem.type is bool:
                return elem.type(
                    True if node.text == "true" else False,
                )
            else:
                return elem.type(node.text)
        else:
            return None

    @classmethod
    def build_initialiser_from_etree_(
        cls,
        api: "BroadworksAPI",  # type: ignore # noqa
        element: etree._Element,
        subelement_set: List[ElementInfo],
        extras: Dict[str, Any] = {},
    ):
        initialiser = extras.copy()
        for elem in subelement_set:
            if elem.is_array:
                result = []
                nodes = element.findall(elem.xmlname)
                for node in nodes:
                    result.append(cls.build_from_node_(api=api, elem=elem, node=node))
                initialiser[elem.name] = result
            else:
                node = element.find(elem.xmlname)
                if node is not None:
                    initialiser[elem.name] = cls.build_from_node_(
                        api=api,
                        elem=elem,
                        node=node,
                    )
                # else:
                # I am inclined to thow an error here - at least after checking if
                # the thing is require, but the class builder should do that so lets
                # let it do its thing
        return initialiser

    @classmethod
    def build_from_etree_(
        cls,
        api: "BroadworksAPI",  # type: ignore # noqa
        element: etree._Element,
        extras: Dict[str, Any] = {},
    ):
        """
        Create an OciType based instance from an XML etree element

        Arguments:
            element: The OCIType XML element

        Returns:
            results: Object instance for this class
        """
        initialiser = cls.build_initialiser_from_etree_(
            api=api,
            element=element,
            subelement_set=list(cls._elements()),
            extras=extras,
        )
        # now have a dict with all the bits in it.
        # use that to build a new object
        return cls(**initialiser)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert object to dict representation of itself

        This was provided as part of the Classforge system, which we have moved away
        from, so this is a local re-implementation.  This is only used within the test
        suite at present.
        """
        elements = {}
        for elem in self._elements():
            value = getattr(self, elem.name)
            if elem.is_table:
                pass
            elif elem.is_complex:
                if elem.is_array:
                    value = [x.to_dict() for x in value]
                elif value is not None:
                    value = value.to_dict()
            elif elem.is_array:
                value = [x for x in value]
            elements[elem.name] = value
        return elements

    def __repr__(self) -> str:
        """Convert object to string representation of itself."""
        dict_form = self.to_dict()
        bits = [f"{key}={repr(dict_form[key])}" for key in dict_form.keys()]
        return f"{self.__class__.__name__}({', '.join(bits)})"

    def __str__(self) -> str:
        """Convert object to string representation of itself."""
        return repr(self)


class OCICommand(OCIType):
    """
    OCICommand - base class for all OCI Command (Request/Response) types

    Attributes:
        session_id (str): The session ID used for the command exchange.
            We use UUIDs by default, although this is not required.  The
            default is fixed on here (but normally passed in from the
            containing API object) - do not use the default in production -
            its simply there to give a known value for testing.
    """

    __slots__: List[str] = ["session_id"]

    def __init__(
        self,
        session_id: str = "00000000-1111-2222-3333-444444444444",
        **kwargs,
    ):
        self.session_id = session_id
        super().__init__(**kwargs)

    def build_xml_(self) -> bytes:
        """
        Build an XML document of the current Command (Request/Response)

        Returns:
            xml: byte string containing XML document
        """
        # document root element
        root = etree.Element(
            "{C}BroadsoftDocument",
            {"protocol": "OCI"},
            nsmap=self._document_nsmap(),
        )
        #
        # add the session
        session = etree.SubElement(root, "sessionId", nsmap=self._default_nsmap())
        session.text = self.session_id
        #
        # and the command
        element = self.build_xml_command_element_(root)
        self.etree_sub_components_(element)  # attach parameters etc
        #
        # wrap a tree around it
        tree = etree.ElementTree(root)
        return etree.tostring(
            tree,
            xml_declaration=True,
            encoding="ISO-8859-1",
            # standalone=False,
            # pretty_print=True,
        )

    def build_xml_command_element_(self, root: etree._Element) -> etree._Element:
        """
        Build the XML etree of the main command element of the current Command
        Intended to be overridden in a subclass for the few elements that do things
        a little differently (for example errors).

        Returns:
            wrapped_element: The wrapped commane element tree
        """
        return etree.SubElement(
            root,
            "command",
            {XSD_TYPE: self.type_},
            nsmap=self._default_nsmap(),
        )

    @classmethod
    def build_from_etree_non_parameters_(
        cls,
        element: etree._Element,
        initialiser: dict,
    ):
        """
        Pick up the session id from the command set

        Overrides the class method defined in OCIType.
        """
        node = element.find("sessionId")
        if node is not None:
            initialiser["session_id"] = node.text

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert object to dict representation of itself

        This was provided as part of the Classforge system, which we have moved away
        from, so this is a local re-implementation.  This is only used within the test
        suite at present.
        """
        elements = super().to_dict()  # pick up the base object data
        return {"session_id": self.session_id, **elements}


class OCIRequest(OCICommand):
    """
    OCIRequest - base class for all OCI Command Request types
    """

    pass


class OCIResponse(OCICommand):
    """
    OCIResponse - base class for all OCI Command Response types
    """

    def build_xml_command_element_(self, root: etree._Element) -> etree._Element:
        """
        Build the XML etree of the main command element of the current Command
        Responses have an echo attribute in the element.

        Returns:
            etree: The XML etree of the main command element
        """
        return etree.SubElement(
            root,
            "command",
            {"echo": "", XSD_TYPE: self.type_},
            nsmap=self._default_nsmap(),
        )


class SuccessResponse(OCIResponse):
    """
    The SuccessResponse is concrete response sent whenever a transaction is successful
    and does not return any data.
    """

    __slots__: List[str] = []

    @classmethod
    def _elements(cls) -> Tuple[ElementInfo, ...]:
        return ()


class ErrorResponse(OCIResponse):
    """
    The ErrorResponse is concrete response sent whenever a transaction fails
    and does not return any data.

    As this an error, when it is created from an incoming command response, a
    `OCIErrorResponse` exception is raised in `post_xml_decode_`.

    Attributes:
        error_code (int): The error code
        summary (str): Summary of the error
        summary_english (str): Summary of the error in english!
        detail (str): Detail of the error
        type (str): Type of the error

    """

    __slots__: List[str] = [
        "error_code",
        "summary",
        "summary_english",
        "detail",
        "type",
    ]

    @classmethod
    def _elements(cls) -> Tuple[ElementInfo, ...]:
        return (
            ElementInfo("error_code", "errorCode", int),
            ElementInfo("summary", "summary", str, is_required=True),
            ElementInfo("summary_english", "summaryEnglish", str, is_required=True),
            ElementInfo("detail", "detail", str),
            ElementInfo("type", "type", str),
        )

    def post_xml_decode_(self):
        """Raise an exception as this is an error"""
        raise OCIErrorResponse(
            object=self,
            message=f"{self.error_code}: {self.summary} - {self.detail}",
        )

    def build_xml_command_element_(self, root):
        return etree.SubElement(
            root,
            "command",
            {
                "type": "Error",
                "echo": "",
                XSD_TYPE: "c:" + self.type_,
            },
            nsmap=self._error_nsmap(),
        )


# end
