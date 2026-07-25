# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/ewjoachim/daily-writing/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                              |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|---------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| daily\_writing/\_\_init\_\_.py    |        0 |        0 |        0 |        0 |    100% |           |
| daily\_writing/\_\_main\_\_.py    |       31 |        3 |       10 |        2 |     88% |32-\>exit, 39-40, 48 |
| daily\_writing/artifacts.py       |       30 |        0 |        2 |        0 |    100% |           |
| daily\_writing/atom.py            |       34 |        0 |        4 |        0 |    100% |           |
| daily\_writing/build.py           |       68 |        0 |       10 |        0 |    100% |           |
| daily\_writing/build\_context.py  |        4 |        0 |        0 |        0 |    100% |           |
| daily\_writing/cms.py             |       96 |        1 |       34 |        3 |     97% |37-\>39, 41-\>43, 84 |
| daily\_writing/fonts.py           |      173 |       22 |       54 |       14 |     82% |56-58, 62-64, 123, 135-\>137, 140, 221-223, 228-230, 236-238, 251-\>250, 255, 260, 262, 276-\>279, 280-\>283, 337, 372 |
| daily\_writing/html.py            |      122 |        2 |       32 |        3 |     97% |79-\>82, 261, 264 |
| daily\_writing/i18n.py            |       27 |        0 |        2 |        0 |    100% |           |
| daily\_writing/models.py          |      256 |       18 |       56 |        7 |     92% |97, 288-289, 298, 410-411, 415, 418-420, 422-423, 462-465, 472-474, 493 |
| daily\_writing/normalize.py       |       44 |       14 |       10 |        2 |     63% |25-44, 74-75, 92-93 |
| daily\_writing/serve.py           |       60 |       41 |        4 |        0 |     30% |    31-111 |
| daily\_writing/settings.py        |      185 |        8 |       24 |        2 |     95% |183-184, 240-242, 303, 514-\>516, 572, 584 |
| daily\_writing/social\_preview.py |       72 |        0 |       16 |        2 |     98% |50-\>53, 53-\>56 |
| daily\_writing/utils.py           |       62 |        0 |       20 |        0 |    100% |           |
| **TOTAL**                         | **1264** |  **109** |  **278** |   **35** | **90%** |           |


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