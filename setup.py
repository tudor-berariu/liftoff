from setuptools import setup

setup(name='liftoff',
      version='0.2',
      description='Experiment launcher; AGI assistant',
      entry_points={
          'console_scripts': [
              'liftoff=liftoff.cmd:launch',
              'liftoff-evolve=liftoff.cmd:evolve',
              'liftoff-prepare=liftoff.cmd:prepare',
              'liftoff-status=liftoff.cmd:status',
              'liftoff-abort=liftoff.cmd:abort',
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
      ],
      zip_safe=False)
