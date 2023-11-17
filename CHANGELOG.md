# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2023.11.16

### Added

- Code for WIndows compatibility in liftoff: launch_run
- Unit tests for liftoff, liftoff-prepare, liftoff-status, liftoff-procs, liftoff-abort
- New parameter CLI flag --skip-confirmation for abort

### Changed

- String manipulation for path replaced with os.path.join
- Some linux terminal specific functions replaced with cross platform python equivalents

### Fixed

- Some string formatting issues
- Path building in 'prepare.py' for cross compatibility with Windows
- Some typos


