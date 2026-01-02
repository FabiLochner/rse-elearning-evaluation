# rse-elearning-evaluation
The goal of this research paper is to evaluate the role of research software within the [DELFI publications](https://dl.gi.de/communities/dc67cfb5-58fd-4aba-bfcd-0f9d3c45635d) of the e-learning community in Germany. 

## Table of Contents
- [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)


## Installation

### Prerequisites

- Python 3.13 or higher
- MySQL Server (for storing extracted paper data)

### Dependencies

This project uses [PyMuPDF](https://github.com/pymupdf/pymupdf) for PDF text extraction. PyMuPDF is licensed under the **GNU Affero General Public License (AGPL-3.0)**. PyMuPDF is installed as a separate dependency via `requirements.txt` and is not distributed with this repository.

All dependencies and their versions are listed in [`requirements.txt`](requirements.txt).

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/rse-elearning-evaluation.git
   cd rse-elearning-evaluation
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```


