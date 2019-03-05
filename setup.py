from setuptools import setup

setup(name='liftoff',
      version='0.22',
      description='Experiment launcher; AGI assistant',
      entry_points={
          'console_scripts': [
              'liftoff=liftoff.cmd:launch',
              'liftoff-prepare=liftoff.cmd:prepare',
              'liftoff-status=liftoff.cmd:status',
              'liftoff-abort=liftoff.cmd:abort',
              'liftoff-commit=liftoff.cmd:commit',
              'liftoff-errors=liftoff.cmd:errors',
              'liftoff-elite=liftoff.cmd:elite',
          ],
      },
      packages=find_packages(),
      url='https://github.com/tudor-berariu/liftoff',
      author='Tudor Berariu',
      author_email='tudor.berariu@gmail.com',
      license='MIT',
      install_requires=[
          'gitpython',
          'pyyaml',
          'tabulate',
          'termcolor',
          'urwid'
      ],
      zip_safe=False)
