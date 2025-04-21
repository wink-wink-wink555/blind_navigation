# Contribution Guidelines

Thank you for your interest in the Tactile Paving Navigation Assistant System project! We welcome all forms of contributions, whether they are code improvements, documentation improvements, problem reports, or feature suggestions.

## Table of Contents

- [Development Environment Setup](#development-environment-setup)
- [Project Architecture](#project-architecture)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Submitting Pull Requests](#submitting-pull-requests)
- [Code Review Process](#code-review-process)
- [Documentation Guidelines](#documentation-guidelines)
- [Reporting Issues](#reporting-issues)
- [Version Control and Release Process](#version-control-and-release-process)
- [Branch Strategy](#branch-strategy)
- [Code of Conduct](#code-of-conduct)
- [Contributors List](#contributors-list)
- [FAQ for Contributors](#faq-for-contributors)

## Development Environment Setup

1. Clone the repository to your local machine:
```bash
git clone https://github.com/wink-wink-wink555/blind-navigation.git
cd blind-navigation
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy the environment variable example file and modify it to your configuration:
```bash
cp .env.example .env
# Edit the .env file and fill in the necessary configuration information
```

5. Download or train the YOLO model and place it in the models/weights directory

6. Set up the database:
```bash
# Create a MySQL database named 'blind_navigation'
mysql -u root -p -e "CREATE DATABASE blind_navigation CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

7. Run the application to verify your setup:
```bash
python app.py
```

## Project Architecture

The Tactile Paving Navigation Assistant System is structured as follows:

- **app.py**: Main application file containing Flask routes and core functionality
- **models/**: Directory containing the YOLO model and related files
  - **weights/**: Trained model weights
- **templates/**: HTML templates for the web interface
- **uploads/**: Directory for storing uploaded videos (created automatically)
- **requirements.txt**: Python dependencies

Key components:

1. **Video Processing**: Handles video uploads and real-time camera feeds
2. **YOLO Model**: Detects tactile paving in video frames
3. **Direction Analysis**: Analyzes the direction of detected tactile paving
4. **Voice Feedback**: Generates and plays voice instructions
5. **User Management**: Handles user authentication and profiles
6. **Location Services**: Manages location sharing and mapping

When making contributions, please consider how your changes fit within this architecture.

## Code Standards

- Please follow the PEP 8 coding standards
- All functions and classes should have clear documentation strings
- Use snake_case for variable and function names
- Use CamelCase for class names
- Run code formatting tools (such as black, flake8) before submitting
- Maximum line length should be 88 characters
- Include type hints where appropriate
- Organize imports in the following order:
  1. Standard library imports
  2. Related third-party imports
  3. Local application imports
- Comment complex algorithms and logic
- Use meaningful variable and function names

Example of well-formatted code:

```python
from typing import List, Dict, Optional
import numpy as np
from flask import request

from .utils import process_image


def detect_paving(image: np.ndarray, threshold: float = 0.5) -> List[Dict]:
    """
    Detect tactile paving in an image.
    
    Args:
        image: The input image as a numpy array
        threshold: Detection confidence threshold
        
    Returns:
        A list of dictionaries containing detection results
    """
    # Implementation details
    results = process_image(image, threshold)
    return results
```

## Testing Guidelines

We use pytest for testing. Please follow these guidelines when writing tests:

1. **Write tests for new features**: All new features should include tests
2. **Test edge cases**: Consider boundary conditions and error cases
3. **Keep tests independent**: Each test should run independently without relying on other tests
4. **Use descriptive test names**: Name tests clearly to describe what they're testing
5. **Use fixtures**: Use pytest fixtures for reusable test components

To run tests:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_detection.py

# Run with coverage report
pytest --cov=app tests/
```

Expected test coverage for new code should be at least 80%.

## Submitting Pull Requests

1. Create a new branch:
```bash
git checkout -b feature/your-feature-name
```

2. Make your changes and commit them:
```bash
git add .
git commit -m "Describe your changes"
```

3. Push to your branch:
```bash
git push origin feature/your-feature-name
```

4. Create a Pull Request on GitHub, describing your changes in detail

When submitting a PR, please:

- Reference any related issues
- Provide a clear description of the changes
- Include screenshots for UI changes
- Ensure all tests pass
- Update documentation if necessary
- Add your name to CONTRIBUTORS.md if it's your first contribution

## Code Review Process

After submitting a PR, the following process will be followed:

1. **Initial review**: Maintainers will review your code within 1-2 business days
2. **Automated checks**: CI/CD pipelines will run automated tests and linting
3. **Review comments**: Reviewers may leave comments requesting changes
4. **Revision**: Make requested changes and push to the same branch
5. **Approval**: Once approved by at least one maintainer, the PR will be merged
6. **Merge**: Maintainers will merge the PR to the appropriate branch

Code reviews will focus on:
- Code quality and adherence to standards
- Test coverage and quality
- Documentation completeness
- Performance considerations
- Security implications

## Documentation Guidelines

Good documentation is crucial for the project. Please follow these guidelines:

1. **Code Documentation**:
   - Use docstrings for all functions, classes, and methods
   - Follow Google Style docstrings format
   - Document parameters, return values, and exceptions

2. **README Updates**:
   - Keep usage examples up to date
   - Document new features
   - Update installation instructions when dependencies change

3. **User Documentation**:
   - Update user guides when adding new features
   - Include screenshots for UI changes
   - Provide examples for API endpoints

4. **Comments**:
   - Comment complex logic
   - Explain "why" rather than "what" (the code shows what, comments explain why)

## Reporting Issues

If you find issues or have feature suggestions, please submit them through GitHub Issues. Please include the following information:

- Detailed description of the issue
- Steps to reproduce (if applicable)
- Expected behavior and actual behavior
- Environment information (operating system, Python version, etc.)
- Possible solutions (if any)
- Screenshots or videos (if relevant)
- Logs or error messages

Use the appropriate issue templates:
- Bug Report: For reporting bugs or unexpected behavior
- Feature Request: For suggesting new features
- Documentation Issue: For issues related to documentation

## Version Control and Release Process

We follow Semantic Versioning (SemVer) for version numbers:

- **MAJOR.MINOR.PATCH** (e.g., 1.2.3)
- Major version: Incompatible API changes
- Minor version: New functionality in a backward-compatible manner
- Patch version: Backward-compatible bug fixes

Release Process:
1. Code freeze on the develop branch
2. Final testing and bug fixing
3. Creation of a release branch
4. Version number update in relevant files
5. Release notes compilation in CHANGELOG.md
6. Merging to main and tagging with version number
7. Building and publishing release artifacts

Contributors can help by:
- Testing release candidates
- Updating documentation for new releases
- Suggesting items for release notes

## Branch Strategy

- `main`: Stable release branch
- `develop`: Development branch, all feature branches branch out from here
- `feature/*`: New feature development
- `bugfix/*`: Fix issues
- `docs/*`: Documentation updates
- `release/*`: Release preparation branches
- `hotfix/*`: Urgent fixes for production

Contributors should typically branch from and create PRs against the `develop` branch.

## Code of Conduct

We are committed to providing a welcoming and inspiring community for all. Our code of conduct includes:

### Expected Behavior

- **Be respectful**: Value each other's ideas, styles, and viewpoints
- **Be open to collaboration**: We work best when we work together
- **Be supportive**: Offer to help others when possible
- **Be constructive**: Provide feedback in a positive and actionable way
- **Be inclusive**: Welcome contributors of all backgrounds and experience levels

### Unacceptable Behavior

- Harassment or discrimination based on personal characteristics
- Aggressive or intimidating behavior
- Derogatory or offensive comments
- Spam or advertising unrelated to the project
- Violation of privacy (sharing personal information without consent)

### Enforcement

Violations of the code of conduct may result in:
1. A warning from project maintainers
2. Temporary restriction from project contributions
3. Permanent removal from the project community

To report violations, contact the project maintainers directly.

## Contributors List

We maintain a CONTRIBUTORS.md file to acknowledge all contributors to the project. When making your first contribution, please add yourself to this file with:

- Your name
- GitHub username
- Type of contribution (code, documentation, bug reports, etc.)

The format should be:

```
- Name: [Your Name](https://github.com/your-username)
  - Contributions: Code, Documentation
  - Role: Contributor
```

## FAQ for Contributors

**Q: How do I know what to work on?**
A: Check the Issues page for tasks labeled "good first issue" or "help wanted".

**Q: Do I need to write tests for small changes?**
A: Yes, all changes that affect functionality should include tests.

**Q: How long will it take for my PR to be reviewed?**
A: We aim to provide initial feedback within 1-2 business days.

**Q: Can I work on multiple issues at once?**
A: It's better to focus on one issue at a time to simplify the review process.

**Q: What if I start working on an issue but can't complete it?**
A: Let us know in the issue comments. It's better to communicate than to leave an issue hanging.

**Q: How do I get help if I'm stuck?**
A: Ask questions in the issue you're working on or reach out on our community channels.

---

Thank you again for your contribution! Your efforts help make this project better for everyone.

Yours sincerely,<br>
wink-wink-wink555
