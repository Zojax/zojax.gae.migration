# -*- coding: utf-8 -*-
"""Setup script."""

import os
from distutils.core import setup


def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

def gen_data_files(*dirs):
    results = []

    for src_dir in dirs:
        for root,dirs,files in os.walk(src_dir):
            results.append((root, map(lambda f:root + "/" + f, files)))
    return results


setup(
    name='zojax.gae.migration',
    version='0.1',
    author="Yaroslav D.",
    author_email='developers@zojax.com',
    description=("""Storage schema migration tool for Google App Engine (Python).
                    Requires Google App Engine to be installed and available in python path.
                """),
    long_description=(
        read('README.rst')
        ),
    license="Apache License 2.0",
    keywords="google app engine gae migration",
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Server',
        ],
    url='',
    packages=['zojax', 'zojax.gae', 'zojax.gae.migration'],
    package_dir = {'': 'src'},
    package_data={'zojax.gae.migration': ['templates/*.html']},
    #data_files = gen_data_files("src/zojax/gae/migration/templates",),
    include_package_data=True,
    namespace_packages=['zojax', 'zojax.gae'],
    install_requires=[
        'distribute',
    ],
    zip_safe=False,
)
