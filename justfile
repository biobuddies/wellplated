set export
set shell := ['bash', '-euo', 'pipefail', '-c']

default:
    @just --list

# print CodeNAme, a four letter acronym
cona:
    #!/usr/bin/env bash
    if [[ $GITHUB_REPOSITORY ]]; then
        echo "${GITHUB_REPOSITORY##*/}"
    elif [[ $VIRTUAL_ENV ]]; then
        basename "${VIRTUAL_ENV%/.venv}"
    else
        basename "$PWD"
    fi

# print ORGanizatioN, a four letter acronym
orgn:
    #!/bin/bash
    if [[ -n ${GITHUB_REPOSITORY_OWNER-} ]]; then
        echo "$GITHUB_REPOSITORY_OWNER";
    else
        git remote get-url origin | sed -E 's,.+github.com/([^/]+).+,\1,';
    fi

# git PUSH over https
push *args:
    git push https://${GITHUB_TOKEN}@github.com/$(just orgn)/$(just cona) {{args}}

# run TESTs and report uncovered lines
test:
    python -m pytest --cov="$(just cona)" --cov-report=term-missing:skip-covered --verbose
