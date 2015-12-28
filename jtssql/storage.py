# -*- coding: utf-8 -*-
from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import io
import csv
import time
from sqlalchemy import Table, Column, MetaData, Text, TEXT, Integer, Float, Boolean
from sqlalchemy.sql import select
from sqlalchemy.schema import CreateSchema
from sqlalchemy.exc import OperationalError
from jsontableschema.model import SchemaModel


# Module API

class Storage(object):

    # Public

    def __init__(self, engine, dbschema=None, prefix=''):

        # Set attributes
        self.__engine = engine
        self.__dbschema = dbschema
        self.__prefix = prefix
        self.__tables_cache = None

    def __repr__(self):

        # Template and format
        template = 'Storage <{name} on {engine}/{dbschema}>'
        text = template.format(
                name = self.__name,
                engine=self.__engine,
                dbschema=dbschema)

        return text

    def __iter__(self):
        return iter(self.__tables)

    def check_table(self, name):
        return name in self.__tables

    def create_table(self, name, schema):
        """Create table by schema.

        Parameters
        ----------
        schema: dict
            BigQuery schema descriptor.

        Raises
        ------
        RuntimeError
            If table is already existent.

        """

        # Add prefix
        name = self.__prefix + name

        # Check not existent
        if self.check_table(name):
            message = 'Table "%s" is already existent.' % self
            raise RuntimeError(message)

        # Convert jts schema
        columns = self.__convert_schema(schema)

        # Create schema
        if self.__dbschema is not None:
            self.__engine.execute(CreateSchema(self.__dbschema))

        # Create table
        metadata = MetaData()
        table = Table(name, metadata, *columns, schema=self.__dbschema)
        table.create(self.__engine)

        # Remove tables cache
        self.__tables_cache = None

    def delete_table(self, name):
        """Delete table.

        Raises
        ------
        RuntimeError
            If table is not existent.

        """

        # Add prefix
        name = self.__prefix + name

        # Check existent
        if self.check_table(name):
            message = 'Table "%s" is not existent.' % self
            raise RuntimeError(message)

        # Drop table
        metadata = MetaData()
        table = Table(self.__name, metadata,
                autoload=True, autoload_with=self.__engine,
                schema=self.__dbschema)
        table.drop(self.__engine)

        # Remove tables cache
        self.__tables_cache = None

    def describe_table(self, name):

        # Add prefix
        name = self.__prefix + name

        metadata = MetaData()
        table = Table(name, metadata,
                autoload=True, autoload_with=self.__engine,
                schema=self.__dbschema)

        # Get schema
        schema = self.__restore_schema(table)

        return schema

    def read_table(self, name):

        # Add prefix
        name = self.__prefix + name

        metadata = MetaData()
        table = Table(name, metadata,
                autoload=True, autoload_with=self.__engine,
                schema=self.__dbschema)

        conn = self.__engine.connect()
        result = conn.execute(select([table]))

        return list(result)

    def write_table(self, name, data):

        # Get model and data
        model = SchemaModel(self.describe_table(name))
        cdata = []
        for row in data:
            rdata = {}
            row = tuple(model.convert_row(*row))
            for index, field in enumerate(model.fields):
                rdata[field['name']] = row[index]
            cdata.append(rdata)

        # Add prefix
        name = self.__prefix + name

        metadata = MetaData()
        table = Table(name, metadata,
                autoload=True, autoload_with=self.__engine,
                schema=self.__dbschema)

        ins = table.insert()
        conn = self.__engine.connect()
        conn.execute(ins, cdata)

    # Private

    @property
    def __tables(self):

        if self.__tables_cache is None:

            # Collect
            names = []
            for name in self.__engine.table_names(schema=self.__dbschema):
                if name.startswith(self.__prefix):
                    name = name.replace(self.__prefix, '', 1)
                    names.append(name)

            # Save
            self.__tables_cache = names

        return self.__tables_cache

    def __convert_schema(self, schema):
        """Convert JSONTableSchema schema to SQLAlchemy columns.
        """

        # Mapping
        mapping = {
            'string': Text(),
            'integer': Integer(),
            'number': Float(),
            'boolean': Boolean(),
        }

        # Convert
        columns = []
        for field in schema['fields']:
            try:
                column_type = mapping[field['type']]
            except KeyError:
                message = 'Type %s is not supported' % field['type']
                raise TypeError(message)
            column = Column(field['name'], column_type)
            columns.append(column)

        return columns

    def __restore_schema(self, table):
        """Convert SQLAlchemy table reflection to JSONTableSchema schema.
        """

        # Mapping
        mapping = {
            TEXT: 'string',
            Integer: 'integer',
            Float: 'number',
            Boolean: 'boolean',
        }

        # Convert
        fields = []
        for column in table.columns:
            try:
                field_type = mapping[column.type.__class__]
            except KeyError:
                message = 'Type %s is not supported' % column.type
                raise TypeError(message)
            field = {'name': column.name, 'type': field_type}
            fields.append(field)
        schema = {'fields': fields}

        return schema
