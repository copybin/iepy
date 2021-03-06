import logging
from tempfile import NamedTemporaryFile
import sys

import factory
import nltk

from iepy.core import Fact, Evidence
from iepy.models import (
    IEDocument, Entity, PreProcessSteps, EntityInSegment,
    TextSegment)


def naive_tkn(text):
    """Makes a naive tokenization returning pairs of tokens and
    offsets. Note, generated offsets are just numbers, to make things easy.
    """
    return list(enumerate(text.split()))


# In general, we are not interested on the debug and info messages
# of Factory-Boy itself
logging.getLogger("factory").setLevel(logging.WARN)


class EntityFactory(factory.Factory):
    FACTORY_FOR = Entity
    key = factory.Sequence(lambda n: 'id:%i' % n)
    canonical_form = factory.Sequence(lambda n: 'Entity #%i' % n)
    kind = 'person'


class EntityInSegmentFactory(factory.Factory):
    FACTORY_FOR = EntityInSegment
    key = factory.Sequence(lambda n: 'id:%i' % n)
    canonical_form = factory.Sequence(lambda n: 'Entity #%i' % n)
    kind = 'person'
    offset = 0
    offset_end = 1


class IEDocFactory(factory.Factory):
    FACTORY_FOR = IEDocument
    human_identifier = factory.Sequence(lambda n: 'doc_%i' % n)
    title = factory.Sequence(lambda n: 'Title for doc %i' % n)
    text = factory.Sequence(lambda n: 'Lorem ipsum yaba daba du! %i' % n)


class TextSegmentFactory(factory.Factory):
    FACTORY_FOR = TextSegment
    document = factory.SubFactory(IEDocFactory)
    text = factory.Sequence(lambda n: 'Lorem ipsum yaba daba du! %i' % n)
    offset = factory.Sequence(lambda n: n * 3)
    offset_end = factory.Sequence(lambda n: n * 3 + 1)
    tokens = ['lorem', 'ipsum', 'dolor']
    postags = ['NN', 'NN', 'V']
    entities = []


class SentencedIEDocFactory(IEDocFactory):
    FACTORY_FOR = IEDocument
    text = factory.Sequence(lambda n: 'Lorem ipsum. Yaba daba du! %i' % n)

    @factory.post_generation
    def init(self, create, extracted, **kwargs):
        tokens = []
        sentences = [0]
        for sent in nltk.sent_tokenize(self.text):
            sent_tokens = nltk.word_tokenize(sent)
            tokens.extend(list(enumerate(sent_tokens)))
            sentences.append(sentences[-1] + len(sent_tokens))

        self.set_preprocess_result(PreProcessSteps.tokenization, tokens)
        self.set_preprocess_result(PreProcessSteps.sentencer, sentences)


def NamedTemporaryFile23(*args, **kwargs):
    """Works exactly as a wrapper to tempfile.NamedTemporaryFile except that
       in python2.x, it excludes the "encoding" parameter when provided."""
    if sys.version_info[0] == 2:  # Python 2
        kwargs.pop('encoding', None)
    return NamedTemporaryFile(*args, **kwargs)


class FactFactory(factory.Factory):
    FACTORY_FOR = Fact
    e1 = factory.SubFactory(EntityFactory)
    e2 = factory.SubFactory(EntityFactory)
    relation = factory.Sequence(lambda n: 'relation:%i' % n)


class EvidenceFactory(factory.Factory):
    """Factory for Evidence instances()

    In addition to the usual Factory Boy behavior, this factory also accepts a
    'markup' argument. The markup is a string with the tokens of the text
    segment separated by entities. You can flag entities by entering them as
    {token token token|kind}. You can also use kind* to flag the first
    occurrence used for the fact, and kind** to flag the second.

    For example, the followingf is valid markup:

    "The physicist {Albert Einstein|Person*} was born in {Germany|location} and
    died in the {United States|location**} ."
    """

    FACTORY_FOR = Evidence
    fact = factory.SubFactory(FactFactory)
    segment = factory.SubFactory(TextSegmentFactory)
    o1 = 0
    o2 = 1

    @classmethod
    def create(cls, **kwargs):
        args = {}
        markup = kwargs.pop('markup', None)
        if markup is not None:
            tokens = []
            entities = []
            while markup:
                if markup.startswith("{"):
                    closer = markup.index("}")
                    entity = markup[1:closer]
                    markup = markup[closer+1:].lstrip()
                    etokens, ekind = entity.split('|')
                    etokens = etokens.split()
                    if ekind.endswith("**"):
                        args["o2"] = len(entities)
                        ekind = ekind[:-2]
                        args["fact__e2__key"] = ' '.join(etokens)
                        args["fact__e2__kind"] = ekind
                    elif ekind.endswith("*"):
                        args["o1"] = len(entities)
                        ekind = ekind[:-1]
                        args["fact__e1__key"] = ' '.join(etokens)
                        args["fact__e1__kind"] = ekind
                    entities.append((etokens, len(tokens), ekind))
                    tokens += etokens
                elif ' ' in markup:
                    token, markup = markup.split(' ', 1)
                    tokens.append(token)
                else:
                    tokens.append(markup)
                    markup = ''
            args["segment__text"] = " ".join(tokens)
            args["segment__tokens"] = tokens
            args["segment__entities"] = [
                EntityInSegmentFactory(key=" ".join(ts), kind=k, offset=o, offset_end=o + len(ts))
                for ts, o, k in entities
            ]

        args.update(kwargs)
        return super(EvidenceFactory, cls).create(**args)

    @factory.post_generation
    def occurrences(self, create, extracted, **kwargs):
        raw_ocurrences = kwargs.pop('data', None)
        if raw_ocurrences is None:
            return
        for entity, offset, offset_end in raw_ocurrences:
            self.segment.entities.append(
                EntityInSegmentFactory(
                    key=entity.key,
                    canonical_form=entity.key,
                    kind=entity.kind,
                    offset=offset,
                    offset_end=offset_end
                ))
