# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/ewjoachim/daily-writing/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                              |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|---------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| daily\_writing/\_\_init\_\_.py    |        0 |        0 |        0 |        0 |    100% |           |
| daily\_writing/\_\_main\_\_.py    |       29 |       29 |       10 |        0 |      0% |      1-44 |
| daily\_writing/artifacts.py       |       30 |        0 |        2 |        0 |    100% |           |
| daily\_writing/atom.py            |       34 |        0 |        4 |        0 |    100% |           |
| daily\_writing/build.py           |       68 |       68 |       10 |        0 |      0% |     1-271 |
| daily\_writing/build\_context.py  |        4 |        4 |        0 |        0 |      0% |       1-6 |
| daily\_writing/cms.py             |       96 |       20 |       34 |        3 |     81% |37-\>39, 41-\>43, 84, 119-138, 145-160, 164 |
| daily\_writing/fonts.py           |      195 |      195 |       52 |        0 |      0% |     1-481 |
| daily\_writing/html.py            |      122 |      122 |       32 |        0 |      0% |     1-549 |
| daily\_writing/i18n.py            |       27 |        8 |        2 |        0 |     66% |22-23, 27, 31, 40, 48-50 |
| daily\_writing/models.py          |      256 |      143 |       56 |        0 |     36% |32, 77-103, 156-158, 183, 189, 193, 197, 200, 204, 208-214, 218-220, 224-229, 232-235, 239, 243-244, 247, 257-267, 280-300, 307-316, 333-374, 387, 400-425, 438-447, 460-481, 485, 489, 493, 497, 501, 505-509, 518, 532, 536, 539, 543 |
| daily\_writing/normalize.py       |       44 |       44 |       10 |        0 |      0% |      1-98 |
| daily\_writing/serve.py           |       59 |       59 |        4 |        0 |      0% |     1-106 |
| daily\_writing/settings.py        |      188 |       31 |       24 |        4 |     82% |145, 176, 181-184, 198, 206, 212, 216-221, 231, 240-242, 303, 513-516, 520, 524, 528, 532, 576, 588, 606 |
| daily\_writing/social\_preview.py |       80 |       80 |       16 |        0 |      0% |     1-141 |
| daily\_writing/utils.py           |       62 |       38 |       20 |        1 |     30% |16-28, 32-41, 45-48, 52-55, 61, 65, 75-77, 86, 90, 97-100 |
| **TOTAL**                         | **1294** |  **841** |  **276** |    **8** | **32%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/ewjoachim/daily-writing/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/ewjoachim/daily-writing/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ewjoachim/daily-writing/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/ewjoachim/daily-writing/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Fewjoachim%2Fdaily-writing%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/ewjoachim/daily-writing/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.