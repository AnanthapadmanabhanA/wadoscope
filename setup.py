from pathlib import Path

from setuptools import find_packages, setup

_here = Path(__file__).parent
_readme = _here / "README.md"
long_description = _readme.read_text(encoding="utf-8") if _readme.exists() else ""

setup(
    name="wadoscope",
    version="0.2.0",
    description="DICOMweb offensive toolkit — QIDO/WADO/STOW recon plus web-layer "
                "checks (unauth, CORS, BOLA, SSRF, stored-XSS) for authorized "
                "medical-imaging testing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Ananthapadmanabhan A",
    url="https://github.com/AnanthapadmanabhanA/wadoscope",
    license="MIT",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.10",
    install_requires=[
        "httpx>=0.27",
        "colorama>=0.4.6",
        "tabulate>=0.9.0",
    ],
    extras_require={
        # pydicom powers the `xss` check's instance synthesis and the lab loader
        "inject": ["pydicom>=2.3"],
    },
    entry_points={
        "console_scripts": [
            "wadoscope = wadoscope.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Healthcare Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Security",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
    ],
    keywords="dicomweb dicom pacs medical imaging security pentest qido wado stow",
)
