from bson import ObjectId, DBRef
import pytest
from datetime import datetime
from marshmallow import ValidationError
from uuid import UUID

from umongo.data_proxy import DataProxy
from umongo import Document, EmbeddedDocument, Schema, EmbeddedSchema, fields, Reference
from umongo.data_objects import List, Dict

from .fixtures import collection_moke, db_moke


class TestFields:

    def test_basefields(self):

        class MySchema(EmbeddedSchema):
            string = fields.StringField()
            uuid = fields.UUIDField()
            number = fields.NumberField()
            integer = fields.IntegerField()
            decimal = fields.DecimalField()
            boolean = fields.BooleanField()
            formattedstring = fields.FormattedStringField('Hello {to_format}')
            float = fields.FloatField()
            # localdatetime = fields.LocalDateTimeField()
            url = fields.UrlField()
            email = fields.EmailField()
            constant = fields.ConstantField("const")

        s = MySchema(strict=True)
        data, err = s.load({
            'string': 'value',
            'uuid': '8c58b5fc-b902-40c8-9d55-e9beb0906f80',
            'number': 1.0,
            'integer': 2,
            'decimal': 3.0,
            'boolean': True,
            'float': 4.0,
            'url': "http://www.example.com/subject",
            'email': "jdoe@example.com",
            'constant': 'forget me'
        })
        assert not err
        assert data == {
            'string': 'value',
            'uuid': UUID('8c58b5fc-b902-40c8-9d55-e9beb0906f80'),
            'number': 1.0,
            'integer': 2,
            'decimal': 3.0,
            'boolean': True,
            'float': 4.0,
            'url': "http://www.example.com/subject",
            'email': "jdoe@example.com",
            'constant': 'const'
        }
        dumped, err = s.dump({
            'string': 'value',
            'uuid': UUID('8c58b5fc-b902-40c8-9d55-e9beb0906f80'),
            'number': 1.0,
            'integer': 2,
            'decimal': 3.0,
            'boolean': True,
            'formattedstring': 'forget me',
            'to_format': 'World',
            'float': 4.0,
            'url': "http://www.example.com/subject",
            'email': "jdoe@example.com",
            'constant': 'forget me'
        })
        assert not err
        assert dumped == {
            'string': 'value',
            'uuid': '8c58b5fc-b902-40c8-9d55-e9beb0906f80',
            'number': 1.0,
            'integer': 2,
            'decimal': 3.0,
            'boolean': True,
            'formattedstring': 'Hello World',
            'float': 4.0,
            'url': "http://www.example.com/subject",
            'email': "jdoe@example.com",
            'constant': 'const'
        }
        with pytest.raises(ValidationError):
            s.load({'to_format': 'not allowed'})

    def test_datetime(self):

        class MySchema(EmbeddedSchema):
            a = fields.DateTimeField()
 
        s = MySchema(strict=True)
        data, _ = s.load({'a': datetime(2016, 8, 6)})
        assert data['a'] == datetime(2016, 8, 6)
        data, _ = s.load({'a': "2016-08-06T00:00:00Z"})
        assert data['a'] == datetime(2016, 8, 6)
        with pytest.raises(ValidationError):
            s.load({'a': "2016-08-06"})
        with pytest.raises(ValidationError):
            s.load({'a': "dummy"})

    def test_dict(self):

        class MySchema(Schema):
            dict = fields.DictField(attribute='in_mongo_dict')

        d = DataProxy(MySchema())
        d.load({'dict': {'a': 1, 'b': {'c': True}}})
        with pytest.raises(KeyError):
            d.get('in_mongo_dict')
        assert d.dump() == {'dict': {'a': 1, 'b': {'c': True}}}
        assert d.get('dict') == {'a': 1, 'b': {'c': True}}
        assert d.to_mongo() == {'in_mongo_dict': {'a': 1, 'b': {'c': True}}}

        # Must manually set_dirty to take the changes into account
        dict_ = d.get('dict')
        dict_['a'] = 1
        assert d.to_mongo(update=True) is None
        dict_.set_modified()
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_dict': {'a': 1, 'b': {'c': True}}}}
        dict_.clear_modified()
        assert d.to_mongo(update=True) is None

        d2 = DataProxy(MySchema(), {'dict': {}})
        d2.to_mongo() == {'dict': {}}

        d3 = DataProxy(MySchema())
        d3.from_mongo({})
        assert isinstance(d3.get('dict'), Dict)
        assert d3.to_mongo() == {}
        assert d3.to_mongo(update=True) is None
        d3.get('dict')['field'] = 'value'
        assert d3.to_mongo(update=True) is None
        d3.get('dict').set_modified()
        assert d3.to_mongo(update=True) == {'$set': {'in_mongo_dict': {'field': 'value'}}}
        assert d3.to_mongo() == {'in_mongo_dict': {'field': 'value'}}

    def test_embedded_document(self):

        class MyEmbeddedDocument(EmbeddedDocument):
            a = fields.IntField(attribute='in_mongo_a')
            b = fields.IntField()

        class MySchema(Schema):
            embedded = fields.EmbeddedField(MyEmbeddedDocument, attribute='in_mongo_embedded')

        # Make sure embedded document doesn't have implicit _id field
        assert '_id' not in MyEmbeddedDocument.Schema().fields
        assert 'id' not in MyEmbeddedDocument.Schema().fields

        d = DataProxy(MySchema())
        d.load(data={'embedded': {'a': 1, 'b': 2}})
        assert d.dump() == {'embedded': {'a': 1, 'b': 2}}
        embedded = d.get('embedded')
        assert type(embedded) == MyEmbeddedDocument
        assert embedded.a == 1
        assert embedded.b == 2
        assert embedded.dump() == {'a': 1, 'b': 2}
        assert embedded.to_mongo() == {'in_mongo_a': 1, 'b': 2}
        assert d.to_mongo() == {'in_mongo_embedded': {'in_mongo_a': 1, 'b': 2}}

        d2 = DataProxy(MySchema())
        d2.from_mongo(data={'in_mongo_embedded': {'in_mongo_a': 1, 'b': 2}})
        assert d == d2

        embedded.a = 3
        assert embedded.to_mongo(update=True) == {'$set': {'in_mongo_a': 3}}
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_embedded': {'in_mongo_a': 3, 'b': 2}}}
        embedded.clear_modified()
        assert embedded.to_mongo(update=True) == None
        assert d.to_mongo(update=True) == None

        del embedded.a
        assert embedded.to_mongo(update=True) == {'$unset': ['in_mongo_a']}
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_embedded': {'b': 2}}}

        d.set('embedded', MyEmbeddedDocument(a=4))
        assert d.get('embedded').to_mongo(update=True) is None
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_embedded': {'in_mongo_a': 4}}}

        embedded_doc = MyEmbeddedDocument(a=1, b=2)
        assert embedded_doc.a == 1
        assert embedded_doc.b == 2
        assert embedded_doc == {'in_mongo_a': 1, 'b': 2}
        assert embedded_doc == MyEmbeddedDocument(a=1, b=2)
        assert embedded_doc['a'] == 1
        assert embedded_doc['b'] == 2

        with pytest.raises(ValidationError):
            MyEmbeddedDocument(in_mongo_a=1, b=2)

        embedded_doc['a'] = 1
        assert embedded_doc.a == embedded_doc['a'] == 1
        del embedded_doc['a']
        assert embedded_doc.a == embedded_doc['a'] == None

        # Test repr readability
        repr_d = repr(MyEmbeddedDocument(a=1, b=2))
        assert 'tests.test_fields.MyEmbeddedDocument' in repr_d
        assert "'in_mongo_a': 1" in repr_d
        assert "'b': 2" in repr_d

    @pytest.mark.xfail()
    def test_embedded_document_required(self):

        class MyEmbeddedDocument(EmbeddedDocument):
            required_field = fields.IntField(required=True)
            optional_field = fields.IntField()

        class MySchema(Schema):
            embedded = fields.EmbeddedField(MyEmbeddedDocument, attribute='in_mongo_embedded')

        with pytest.raises(ValidationError):
            MyEmbeddedDocument()

        with pytest.raises(ValidationError):
            MyEmbeddedDocument(optional_field=1)
        embedded = MyEmbeddedDocument(optional_field=1, required_field=2)
        d = DataProxy(MySchema())

    def test_list(self):

        class MySchema(Schema):
            list = fields.ListField(fields.IntField(), attribute='in_mongo_list')

        d = DataProxy(MySchema())
        assert d.to_mongo() == {}

        d.load({'list': [1, 2, 3]})
        assert d.dump() == {'list': [1, 2, 3]}
        assert d.to_mongo() == {'in_mongo_list': [1, 2, 3]}
        assert d.get('list') == [1, 2, 3]
        d.get('list').append(4)
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_list': [1, 2, 3, 4]}}

        d.clear_modified()
        d.set('list', [5, 6, 7])
        assert d.dump() == {'list': [5, 6, 7]}
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_list': [5, 6, 7]}}

        d.clear_modified()
        d.get('list').pop()
        assert d.dump() == {'list': [5, 6]}
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_list': [5, 6]}}

        d.clear_modified()
        d.get('list').clear()
        assert d.dump() == {'list': []}
        assert d.to_mongo(update=True) == {'$unset': ['in_mongo_list']}

        d.set('list', [1, 2, 3])
        d.clear_modified()
        d.get('list').remove(1)
        assert d.dump() == {'list': [2, 3]}
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_list': [2, 3]}}

        d.clear_modified()
        d.get('list').reverse()
        assert d.dump() == {'list': [3, 2]}
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_list': [3, 2]}}

        d.clear_modified()
        d.get('list').sort()
        assert d.dump() == {'list': [2, 3]}
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_list': [2, 3]}}

        d.clear_modified()
        d.get('list').extend([4, 5])
        assert d.dump() == {'list': [2, 3, 4, 5]}
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_list': [2, 3, 4, 5]}}

        d2 = DataProxy(MySchema())
        d2.from_mongo({})
        assert isinstance(d2.get('list'), List)
        assert d2.to_mongo() == {}
        d2.get('list').append(1)
        assert d2.to_mongo() == {'in_mongo_list': [1]}
        assert d2.to_mongo(update=True) == {'$set': {'in_mongo_list': [1]}}

        # Test repr readability
        repr_d = repr(d.get('list'))
        assert repr_d == "<object umongo.data_objects.List([2, 3, 4, 5])>"

    def test_complexe_list(self):

        class MyEmbeddedDocument(EmbeddedDocument):
            field = fields.IntField()

        class ToRefDoc(Document):
            pass

        class MySchema(Schema):
            embeds = fields.ListField(fields.EmbeddedField(MyEmbeddedDocument))
            refs = fields.ListField(fields.ReferenceField(ToRefDoc))

        obj_id1 = ObjectId()
        obj_id2 = ObjectId()
        to_ref_doc1 = ToRefDoc.build_from_mongo(data={'_id': obj_id1})
        d = DataProxy(MySchema())
        d.load({
            'embeds': [MyEmbeddedDocument(field=1),
                       {'field': 2}],
            'refs': [to_ref_doc1, Reference(ToRefDoc, obj_id2)]
        })
        assert d.to_mongo() == {
            'embeds': [{'field': 1}, {'field': 2}],
            'refs': [obj_id1, obj_id2]
        }
        assert isinstance(d.get('embeds'), List)
        assert isinstance(d.get('refs'), List)
        for e in d.get('refs'):
            assert isinstance(e, Reference)
        for e in d.get('embeds'):
            assert isinstance(e, MyEmbeddedDocument)
        # Test list modification as well
        refs_list = d.get('refs')
        refs_list.append(to_ref_doc1)
        refs_list.extend([to_ref_doc1, Reference(ToRefDoc, obj_id2)])
        for e in refs_list:
            assert isinstance(e, Reference)
        embeds_list = d.get('embeds')
        embeds_list.append(MyEmbeddedDocument(field=3))
        embeds_list.extend([{'field': 4}, {'field': 5}])
        for e in embeds_list:
            assert isinstance(e, MyEmbeddedDocument)

    def test_objectid(self):

        class MySchema(Schema):
            objid = fields.ObjectIdField(attribute='in_mongo_objid')

        d = DataProxy(MySchema())
        d.load({'objid': ObjectId("5672d47b1d41c88dcd37ef05")})
        assert d.dump() == {'objid': "5672d47b1d41c88dcd37ef05"}
        assert d.to_mongo() == {'in_mongo_objid': ObjectId("5672d47b1d41c88dcd37ef05")}
        d.load({'objid': "5672d47b1d41c88dcd37ef05"})
        assert d.dump() == {'objid': "5672d47b1d41c88dcd37ef05"}
        assert d.to_mongo() == {'in_mongo_objid': ObjectId("5672d47b1d41c88dcd37ef05")}
        assert d.get('objid') == ObjectId("5672d47b1d41c88dcd37ef05")

        d.set('objid', ObjectId("5672d5e71d41c88f914b77c4"))
        d.to_mongo(update=True) == {
            '$set': {'in_mongo_objid': ObjectId("5672d5e71d41c88f914b77c4")}}

        d.set('objid', ObjectId("5672d5e71d41c88f914b77c4"))
        d.to_mongo(update=True) == {
            '$set': {'in_mongo_objid': ObjectId("5672d5e71d41c88f914b77c4")}}

        d.set('objid', "5672d5e71d41c88f914b77c4")
        assert d.get('objid') == ObjectId("5672d5e71d41c88f914b77c4")

        with pytest.raises(ValidationError):
            d.set('objid', 'notanid')

    def test_reference(self, collection_moke):

        class MyReferencedDoc(Document):

            class Meta:
                collection = collection_moke

        class OtherDoc(Document):
            pass

        to_refer_doc = MyReferencedDoc.build_from_mongo(
            {'_id': ObjectId("5672d47b1d41c88dcd37ef05")})
        ref = Reference(MyReferencedDoc, to_refer_doc.pk)
        dbref = DBRef(collection_moke.name, to_refer_doc.pk)
        other_doc = OtherDoc.build_from_mongo(
            {'_id': ObjectId("5672d47b1d41c88dcd37ef07")})

        # Test reference equality
        assert ref == to_refer_doc
        assert ref == dbref
        assert dbref == to_refer_doc
        assert dbref == ref
        assert to_refer_doc == ref
        assert to_refer_doc == dbref

        class MySchema(Schema):
            ref = fields.ReferenceField(MyReferencedDoc, attribute='in_mongo_ref')

        d = DataProxy(MySchema())
        d.load({'ref': ObjectId("5672d47b1d41c88dcd37ef05")})
        d.load({'ref': "5672d47b1d41c88dcd37ef05"})
        assert d.dump() == {'ref': "5672d47b1d41c88dcd37ef05"}
        d.get('ref').document_cls == MyReferencedDoc
        d.set('ref', to_refer_doc)
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_ref': to_refer_doc.pk}}
        assert d.get('ref') == ref
        d.set('ref', ref)
        assert d.get('ref') == ref
        d.set('ref', dbref)
        assert d.get('ref') == ref

        with pytest.raises(ValidationError):
            d.set('ref', other_doc)
        not_created_doc = MyReferencedDoc()
        with pytest.raises(ValidationError):
            d.set('ref', not_created_doc)
        bad_ref = Reference(OtherDoc, other_doc.pk)
        with pytest.raises(ValidationError):
            d.set('ref', bad_ref)

    def test_reference_lazy(self):

        class MyReferencedDocLazy(Document):
            pass

        to_refer_doc = MyReferencedDocLazy.build_from_mongo(
            {'_id': ObjectId("5672d47b1d41c88dcd37ef05")})

        class MySchema(Schema):
            ref = fields.ReferenceField("MyReferencedDocLazy", attribute='in_mongo_ref')

        d = DataProxy(MySchema())
        d.load({'ref': ObjectId("5672d47b1d41c88dcd37ef05")})
        d.load({'ref': "5672d47b1d41c88dcd37ef05"})
        assert d.dump() == {'ref': "5672d47b1d41c88dcd37ef05"}
        assert d.get('ref').document_cls == MyReferencedDocLazy
        d.set('ref', to_refer_doc)
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_ref': to_refer_doc.pk}}
        assert d.get('ref').document_cls == MyReferencedDocLazy

    def test_generic_reference(self, db_moke):

        class ToRef1(Document):

            class Config:
                collection = db_moke.col_ref1

        class ToRef2(Document):

            class Config:
                collection = db_moke.col_ref2

        doc1 = ToRef1.build_from_mongo({'_id': ObjectId()})
        ref1 = Reference(ToRef1, doc1.pk)

        class MySchema(Schema):
            gref = fields.GenericReferenceField(attribute='in_mongo_gref')

        d = DataProxy(MySchema())
        d.load({'gref': {'id': ObjectId("5672d47b1d41c88dcd37ef05"), 'cls': ToRef2.__name__}})
        assert d.dump() == {'gref': {'id': "5672d47b1d41c88dcd37ef05", 'cls': 'ToRef2'}}
        d.get('gref').document_cls == ToRef2
        d.set('gref', doc1)
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_gref': {'_id': doc1.pk, '_cls': 'ToRef1'}}}
        assert d.get('gref') == ref1
        d.set('gref', ref1)
        assert d.get('gref') == ref1
        assert d.dump() == {'gref': {'id': str(doc1.pk), 'cls': 'ToRef1'}}

        not_created_doc = ToRef1()
        with pytest.raises(ValidationError):
            d.set('gref', not_created_doc)

        # Test invalid references
        for v in [
                {'id': ObjectId()},  # missing _cls
                {'cls': ToRef1.__name__},  # missing _id
                {'id': ObjectId(), 'cls': 'dummy!'},  # invalid _cls
                {'_id': ObjectId(), '_cls': ToRef1.__name__},  # bad field names
                {'id': ObjectId(), 'cls': ToRef1.__name__, 'e': '?'},  # too much fields
                ObjectId("5672d47b1d41c88dcd37ef05"),  # missing cls info
                42,  # Are you kidding ?
                '',  # Please stop...
                True  # I'm outa of that !
                ]:
            with pytest.raises(ValidationError) as exc:
                d.set('gref', v)
