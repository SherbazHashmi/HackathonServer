
# -*- coding: utf-8 -*-
import re
import sys

from netCDF4.utils import ncinfo

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(ncinfo())
