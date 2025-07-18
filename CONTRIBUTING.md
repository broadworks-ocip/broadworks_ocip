# Contributing

Contributions are welcome, and they are greatly appreciated! Every little bit
helps, and credit will always be given.

You can contribute in many ways:

## Report Bugs

Report bugs at https://github.com/nigelm/broadworks_ocip/issues.

If you are reporting a bug, please include:

-   Your operating system name and version.
-   Any details about your local setup that might be helpful in troubleshooting.
-   Detailed steps to reproduce the bug.

## Fix Bugs

Look through the GitHub issues for bugs. Anything tagged with "bug" and "help
wanted" is open to whoever wants to implement it.

## Implement Features

Look through the GitHub issues for features. Anything tagged with "enhancement"
and "help wanted" is open to whoever wants to implement it.

## Write Documentation

`broadworks_ocip` could always use more documentation, whether as part of the
official docs, in docstrings, or even on the web in blog posts, articles, and
such.

## Submit Feedback

The best way to send feedback is to file an issue at https://github.com/nigelm/broadworks_ocip/issues.

If you are proposing a feature:

-   Explain in detail how it would work.
-   Keep the scope as narrow as possible, to make it easier to implement.
-   Remember that this is a volunteer-driven project, and that contributions
    are welcome :)

## Get Started!

Ready to contribute? Here's how to set up `broadworks_ocip` for local development.

1. Fork the `broadworks_ocip` repo on GitHub.

2. Clone your fork locally:

```bash
$ git clone git@github.com:your_name_here/broadworks_ocip.git
```

3. We use [`uv`](https://python-uv.org/) for development, this is how you set up your
   fork for local development

```bash
$ cd broadworks_ocip/
$ uv sync
```

4. Create a branch for local development:

```bash
$ git checkout -b name-of-your-bugfix-or-feature
```

Now you can make your changes locally.

5. If you update schemas or modify `process_schema.py`, you must regenerate
   the generated python code:

```bash
$ make code
```

6. When you're done making changes, use pre-commit to do basic checks and ensure formatting
   is consistant, and check that your changes pass the tests::

```bash
$ git add .; pre-commit run
$ make test
$ make servdocs    # generate local docs for checking
```

`pre-commit` may need to be installed onto your system.

7. Commit your changes and push your branch to GitHub:

```bash
$ git add .
$ git commit -m "Your detailed description of your changes."
$ git push origin name-of-your-bugfix-or-feature
```

8. Submit a pull request through the GitHub website.

# Deploying

This is now handled by github actions - there is a manual release action.
