
# PYTHONTOOLS

Lightweight python tools for **Sublime Text**.

# FEATURES

- **Completion**
- **Documentation**
- **Document formatting**
- **Rename**
- **Linter** 

# SETUP

## Plugin

Download [release](https://github.com/ginanjarn/pythontools/archive/master.zip) version from github or clone `https://github.com/ginanjarn/pythontools.git` to **Sublime Text `package directory`**.

> `Preferences` -> `Browse Packages`

## Python

Install any **python** distribution and **required packages**.

## Required packages

- `jedi`
- `black`
- `pylint`
- `pyflakes`
- `rope`

> Install command:
> * Conda : `conda instal <package-name>`
> * Pip : `pip install <package-name>`

# USAGE

## Preparation

1. Setup **`python interpreter`**. Open command palette (`Ctrl+Shift+P`) `->` `Python Interpreter`.

> Interpreter scan in `PATH` and `Anaconda PATH`.

2. Install [required packages](#Required_Packages).

## Commands

|No|Command|Function|
|--|--|--|
|1|`Pytools: Python Interpreter`|setup interpreter|
|2|`Pytools: Format document`|format document|
|3|`Pytools: Rename`|rename selected idetifier|
|4|`Pytools: Lint document`|lint using pylint|
|5|`Pytools: Lint(PyFlakes)`|lint using pyflakes|
|6|`Pytools: Clean lint message`|clean lint message|
|7|`Pytools: Open Terminal`|open terminal in current project|
|8|`Pytools: Open Terminal Here`|open terminal in active document directory|
|9|`Pytools: Run server`|run plugin server|
|10|`Pytools: Shutdown server`|shutdown plugin server|

> Plugin server will started if hover in python identifier or typing. Server *still running* even Sublime Text closed. You have to shutdown manually.

## Feature Options

Feature can be disabled by uncheck menu `Preferences` -> `Package Settings` -> `Python tools`.

# TROUBLESHOOT

* This plugin conflict with other python completion plugin. Try to disable or remove the plugin.
* Install [required packages](#setup).

## LICENSE

Copyright (c) 2021 ginanjarn.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
