
# -*- coding: utf-8 -*-
import re
import sys

from netCDF4.utils import nc4tonc3

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(nc4tonc3())
