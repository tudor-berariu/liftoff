from setuptools import setup

setup(name='liftoff',
      version='0.02',
      description='Experiment launcher; AGI assistant',
      entry_points={
          'console_scripts': [
              'liftoff=liftoff.cmd:launch',
              'liftoff-prepare=liftoff.cmd:prepare',
              'liftoff-status=liftoff.cmd:status',
              'liftoff-abort=liftoff.cmd:abort',
              'liftoff-commit=liftoff.cmd:commit',
              'liftoff-errors=liftoff.cmd:errors',
          ],
      },
      url='https://github.com/tudor-berariu/liftoff',
      author='Tudor Berariu',
      author_email='tudor.berariu@gmail.com',
      license='MIT',
      packages=['liftoff'],
      install_requires=[
          'pyyaml',
          'tabulate',
          'termcolor',
          'urwid'
      ],
      zip_safe=False)
