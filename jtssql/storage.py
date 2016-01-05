# -*- coding: utf-8 -*-
from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import six
from sqlalchemy import Table, Column, MetaData, Text, Integer, Float, Boolean
from jsontableschema.model import SchemaModel


# Module API

class Storage(object):

    # Public

    def __init__(self, engine, dbschema=None, prefix=''):

        # Set attributes
        self.__engine = engine
        self.__dbschema = dbschema
        self.__prefix = prefix

        # Create metadata
        self.__metadata = MetaData(
                bind=self.__engine,
                schema=self.__dbschema,
                reflect=True)

    def __repr__(self):

        # Template and format
        template = 'Storage <{engine}/{dbschema}>'
        text = template.format(
                engine=self.__engine,
                dbschema=self.__dbschema)

        return text

    @property
    def tables(self):
        """Return list of storage's table names.
        """

        # Collect
        tables = []
        for dbtable in self.__metadata.tables.values():
            table = dbtable.name
            table = _restore_table(table, self.__prefix)
            tables.append(table)

        return tables

    def check(self, table):
        """Return if table exists.
        """

        # Check existence
        existence = table in self.tables

        return existence

    def create(self, table, schema):
        """Create table by schema.

        Parameters
        ----------
        table: str/list
            Table name or list of table names.
        schema: dict/list
            JSONTableSchema descriptor or list of them.

        Raises
        ------
        RuntimeError
            If table already exists.

        """

        # Make lists
        tables = table
        if isinstance(table, six.string_types):
            tables = [table]
        schemas = schema
        if isinstance(schema, dict):
            schemas = [schema]

        # Iterate over tables/schemas
        for table, schema in zip(tables, schemas):

            # Check not existent
            if self.check(table):
                message = 'Table "%s" already exists.' % table
                raise RuntimeError(message)

            # Define table
            table = _convert_table(table, self.__prefix)
            columns, constraints = _convert_schema(schema)
            Table(table, self.__metadata, *(columns+constraints))

        # Create tables, update metadata
        self.__metadata.create_all()
        # Metadata reflect is auto

    def delete(self, table):
        """Delete table.

        Parameters
        ----------
        table: str/list
            Table name or list of table names.

        Raises
        ------
        RuntimeError
            If table is not existent.

        """

        # Make lists
        tables = table
        if isinstance(table, six.string_types):
            tables = [table]

        # Iterate over tables
        targets = []
        for table in tables:

            # Check existent
            if not self.check(table):
                message = 'Table "%s" is not existent.' % self
                raise RuntimeError(message)

            # Add table to targets
            table = _convert_table(table, self.__prefix)
            targets.append(table)

        # Drop tables, update metadata
        self.__metadata.drop_all(tables=[targets])
        self.__metadata.reflect()

    def describe(self, table):
        """Return table's JSONTableSchema descriptor.
        """

        # Get schema
        dbtable = self.__get_dbtable(table)
        schema = _restore_schema(dbtable.columns, dbtable.constraints)

        return schema

    def read(self, table):
        """Return table's data.
        """

        # Get result
        dbtable = self.__get_dbtable(table)
        result = dbtable.select().execute()

        # Get data
        data = []
        schema = self.describe(table)
        model = SchemaModel(schema)
        for row in result:
            row = tuple(model.convert_row(*row))
            data.append(row)

        return data

    def write(self, table, data):
        """Write data to table.
        """

        # Process data
        schema = self.describe(table)
        model = SchemaModel(schema)
        cdata = []
        for row in data:
            rdata = {}
            row = tuple(model.convert_row(*row))
            for index, field in enumerate(model.fields):
                rdata[field['name']] = row[index]
            cdata.append(rdata)

        # Insert data
        dbtable = self.__get_dbtable(table)
        dbtable.insert().execute(cdata)

    # Private

    def __get_dbtable(self, table):
        """Return dbtable instance from metadata.
        """

        # Prepare dict key
        key = _convert_table(table, self.__prefix)
        if self.__dbschema:
            key = '.'.join(self.__dbschema, key)

        return self.__metadata.tables[key]


# Internal

def _convert_table(table, prefix):
    """Convert high-level table name to database name.
    """
    return prefix + table


def _restore_table(table, prefix):
    """Restore database table name to high-level name.
    """
    return table.replace(prefix, '', 1)


def _convert_schema(schema):
    """Convert JSONTableSchema schema to SQLAlchemy columns and constraints.
    """

    # Mapping
    mapping = {
        'string': Text(),
        'integer': Integer(),
        'number': Float(),
        'boolean': Boolean(),
    }

    # Columns
    columns = []
    for field in schema['fields']:
        try:
            column_type = mapping[field['type']]
        except KeyError:
            message = 'Type %s is not supported' % field['type']
            raise TypeError(message)
        column = Column(field['name'], column_type)
        columns.append(column)

    # Constraints
    constraints = []

    return (columns, constraints)


def _restore_schema(columns, constraints):
    """Convert SQLAlchemy columns and constraints to JSONTableSchema schema.
    """

    # Mapping
    mapping = {
        Text: 'string',
        Integer: 'integer',
        Float: 'number',
        Boolean: 'boolean',
    }

    # Convert
    fields = []
    for column in columns:
        try:
            field_type = mapping[column.type.__class__]
        except KeyError:
            message = 'Type %s is not supported' % column.type
            raise TypeError(message)
        field = {'name': column.name, 'type': field_type}
        fields.append(field)
    schema = {'fields': fields}

    return schema
