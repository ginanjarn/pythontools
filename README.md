# PYTOOLS

Lightweight python tools for Sublime Text.

---

## FEATURES

- **Completion**

- **Documentation**

- **Document formatting**

- **Linter** 

---

## SETUP

### Plugin

Download [release](https://github.com/ginanjarn/pythontools/archive/master.zip) version from github or clone `https://github.com/ginanjarn/pythontools.git`  to *SublimeText* `package directory`.

> On **SublimeText** : `Preferences -> Browse Packages` to open `package directory`.

### Python

Install any **python** distribution, prefer **anaconda** easy to use with many included package.

Install following requires packages:

- **jedi**

- **black**

- **pylint**

> Install command:
> 
> `conda instal <package-name>` if use `conda` or `pip install <package-name>` if use `pip`.

---

## USAGE

#### Preparation

1. Setup **`python interpreter`**. Open command palette (`Ctrl+Shift+P`). `-> Python Interpreter`.

> *System installed* **python** and *default installation* **anaconda** automatically detected. Manual input path required if not any **interpreter** found.

2. Setup activated feature(Optional).  Open command palette by`Ctrl+Shift+P`. Run `Feature Config`.

#### Completion

Completion show on typing source.

#### Documentation

Hover above identifier word to show documentation.

#### Format code

Open command palette (`Ctrl+Shift+P`) `-> Format document`.

#### Linting

Open command palette (`Ctrl+Shift+P`) `-> Lint module`.

---

## TROUBLESHOOT

* This plugin conflic with other pyhon completion plugin. Try to disable or remove thr plugin.

* Python must be setup. Manual setting on `$SUBLIMETEXT_PACKAGE_DIRECTORY/User/Pythools.sublime-settings`.

* Required `python package` : `jedi, black, pylint`.

## LICENSE

`Copyright (c) 2021 ginanjarn
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.`
