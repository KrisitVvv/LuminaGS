import warnings
from setuptools import SetuptoolsDeprecationWarning
from setuptools.command.easy_install import EasyInstallDeprecationWarning

# 忽略指定类型的警告
warnings.filterwarnings("ignore", category=SetuptoolsDeprecationWarning)
warnings.filterwarnings("ignore", category=EasyInstallDeprecationWarning)