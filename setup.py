from setuptools import setup


with open('requirements.txt', 'r') as f:
    lines = f.readlines()
    requirements = [l.strip().strip('\n') for l in lines if l.strip() and not l.strip().startswith('#')]

scripts = ["trackpage", "bvr", "imapfile", "gnucash2hledger", "zotexport", "radio", "readinglist2ebook", "text2ics", "tv"]

setup(name="frinkelpi-scripts",
      version="0.1",
      author="frinkelpi",
      license="MIT",
      packages=scripts + ["utils"],
      entry_points={"console_scripts": ["{0}={0}.{0}:main".format(s) for s in scripts]},
      install_requires=requirements,
      zip_safe=False)
