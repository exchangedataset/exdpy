# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SPHINXAPIDOC  ?= sphinx-apidoc
SOURCEDIR     = .
MODULEDIR     = ../exdpy
BUILDDIR      = _build

.PHONY: help Makefile

# Generates documentation for Github Pages.
all:
	@rm -rf ../docs
	@${SPHINXAPIDOC} -fo "${BUILDDIR}/exdpy" "${MODULEDIR}"
	@$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
	@cp -r "$(BUILDDIR)/html" ../docs
	@touch ../docs/.nojekyll
