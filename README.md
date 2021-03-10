# PYTHONTOOLS

Lightweight python tools for **SublimeText**.

---

## FEATURES

- **Completion**

- **Documentation**

- **Document formatting**

- **Linter** 

---

## SETUP

### Plugin

Download [release](https://github.com/ginanjarn/pythontools/archive/master.zip) version from github or clone `https://github.com/ginanjarn/pythontools.git` to **SublimeText** `package directory`.

> On **SublimeText** : `Preferences` `->` `Browse Packages` to open `PACKAGES directory`.

### Python

Install any **python** distribution, prefer **anaconda** python distribution with battery-included package.

Install following required packages:

- **jedi**

- **black**

- **pylint**

> Install command:
> 
> * Conda         : `conda instal <package-name>`
> 
> * Pip         : `pip install <package-name>`

---

## USAGE

### Preparation

1. Setup **`python interpreter`**. Open command palette (`Ctrl+Shift+P`) `->` `Python Interpreter`.

> Interpreter scan in `PATH` and `Anaconda PATH`.

2. Install [required packages](#Python). Bypass if already installed.

3. Configure **disabled** features (*Optional*).  Open command palette `(Ctrl+Shift+P)` `->` `Feature Config`.

> Default all features **enabled**.

### Completion

Completion pop-up while typing.

### Documentation

Hover above identifier show documentation pop-up.

### Format code

Open command palette (`Ctrl+Shift+P`) `->` `Format document`.

> Notice: check formatting changes before save to prevent future bugs.

### Linting

Open command palette (`Ctrl+Shift+P`) `->` `Lint module`.

---

## TROUBLESHOOT

* This plugin conflict with other python completion plugin. Try to disable or remove the plugin.

* Python interpreter must be setup.
  
  Manual setting on `PACKAGES/User/Pytools.sublime-settings`.

* Required `python package` : `jedi`, `black`, `pylint`.

## LICENSE

`Copyright (c) 2021 ginanjarn.
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
