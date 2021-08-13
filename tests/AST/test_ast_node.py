import argparse
import logging
import os
import sys

import textx

from dsl import node

logging.basicConfig(level=logging.WARNING,
                    format='%(levelname)s:%(name)s:%(lineno)d: %(message)s')
logger = logging.getLogger().getChild(os.path.basename(__file__))

def main():
    parser = argparse.ArgumentParser(
        prog='test_textx',
        description='Test dsl grammar with a input DSL test file'
    )
    parser.add_argument(
        '--dsl',
        type=str,
        dest='dsl_def'
    )
    parser.add_argument(
        '--with',
        type=str,
        dest='test_file'
    )

    logging.getLogger().setLevel(logging.DEBUG)
    logger.info('Begin Logging:')

    ''' Parse input program'''
    args = parser.parse_args()
    if args.dsl_def == None or args.test_file == None:
        logger.info('Lack of file input')
    else:
        logger.info('DSL Defination: %s,', args.dsl_def)
        logger.info('Test File: %s', args.test_file)

    dsl_mm = textx.metamodel_from_file(args.dsl_def, classes=node.CLASSES)
    dsl_m = dsl_mm.model_from_file(args.test_file)

    logger.info('Program successfully parsed:\n %s',
                str(dsl_m).replace('\n', '\n '))

if __name__ == '__main__':
    main()