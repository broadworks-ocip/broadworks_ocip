# Broadworks OCI-P Interface

[![Tests](https://github.com/nigelm/broadworks_ocip/workflows/Tests/badge.svg)](https://github.com/nigelm/broadworks_ocip/actions?workflow=Tests)
[![documentation](https://img.shields.io/badge/docs-mkdocs%20material-blue.svg?style=flat)](https://broadworks-ocip.github.io/broadworks_ocip/)
[![pypi version](https://img.shields.io/pypi/v/broadworks_ocip.svg)](https://pypi.python.org/pypi/broadworks_ocip)

`broadworks_ocip` interfaces to the OCI-P provisioning interface of a Broadworks softswitch

-   Free software: BSD license
-   Documentation: https://broadworks-ocip.github.io/broadworks_ocip/

---

> [!NOTE]
> I no longer have time or access to Broadworks to be able to maintain this package.
> If you would like to take it on let me know.
> For now I am archiving the respository to make it clear that this now unmaintained.

---

## Features

-   python objects to match all Broadworks schema objects
-   API framework to talk to a Broadworks server
-   additional magic to handle authentication and sessions
-   Based on Broadworks schema R25

## Current Version

Version: `2.2.0`

This is based on Broadworks schema R25 - the available methods will have changed based on that.

---

## Installation

With `pip`:

```bash
python3 -m pip install broadworks-ocip
```

---

## Usage

More details is given within the usage section of the documentation, but the
minimal summary is:-

```python
from broadworks_ocip import BroadworksAPI

# configure the API, connect and authenticate to the server
api = BroadworksAPI(
    host=args.host, port=args.port, username=args.username, password=args.password,
)

# get the platform software level
response = api.command("SystemSoftwareVersionGetRequest")
print(response.version)
```

## Version 2

Despite the bump in version number there are no known major incompatibilities
from previous versions. However the underlying class base has been changed
to a vanilla python slots based system - the thinking behind this is in the
API internals documentation. This will change the underlying requirements.

Additionally at the same time I have converted to Broadworks R24 API schema
files as the basis for generating these classes. This will change the set of
available commands and classes.

## Credits

The class used to be built using Michael DeHaan's [`ClassForge`]
(https://classforge.io/) object system, however from version 2.0.0 it has
been based on vanilla python slotted objects.

Development on the python version was done by
[Nigel Metheringham `<nigelm@cpan.org>`](https://github.com/nigelm/)

Karol Skibiński has been using the package, and has a talent for both finding
bugs within it and providing a good bug report that allows a test case and fix
to be made. The package has been immensely improved by this work.

R25 schema update along with some other changes was contributed by
[@ewurch (Eduardo Würch)](https://github.com/ewurch).

---
