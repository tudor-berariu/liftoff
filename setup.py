from setuptools import setup

setup(name='liftoff',
      version='0.01',
      description='Experiment launcher; AGI assistant',
      entry_points={
          'console_scripts': [
              'liftoff=liftoff.cmd:launch',
              'liftoff-prepare=liftoff.cmd:prepare'
          ],
      },
      url='https://github.com/tudor-berariu/liftoff',
      author='Tudor Berariu',
      author_email='tudor.berariu@gmail.com',
      license='MIT',
      packages=['liftoff'],
      zip_safe=False)
