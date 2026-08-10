# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [0.1.6] - 2026-08-10

- CI pipeline change

## [0.1.5] - 2026-08-10

- Fix sense2vec installation: use STELINT_S2V_PATH env var with manual extraction
- Rename SENSE2VEC_PATH to STELINT_S2V_PATH for namespacing
- Remove noisy progress messages from spaCy model loading
- Add spaCy model info to --help output
- Add sense2vec instructions to --help output
- Add specific download URL and extraction instructions to --help

## [0.1.4] - 2026-08-10

### Breaking changes

- Stdin reading now requires explicit `-` argument. Running `stelint` without arguments shows usage instead of hanging.

### What's new

- `--help` flag shows usage information

## [0.1.3] - 2026-08-10

- Add sense2vec dependency and make model loading optional

## [0.1.2] - 2026-08-10

- Fixes to NLP model loading with stelint module (python -m spacy download en_core_web_sm)

## [0.1.1] - 2026-08-10

- Cosmetic fixes

## [0.1.0] - 2026-08-10

- Proof-of-concept version for evaluation of further development
