from setuptools import setup, Extension

module = Extension(
    'autoschedulemodule',       
    sources=['autoschedulemodule.c'], 
    extra_compile_args=[],    
)

setup(
    name="autoschedulemodule",
    version='1.0',
    description='Scheduling Algorithm Module',
    ext_modules=[module],
)
