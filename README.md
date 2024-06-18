# syntaxcomp
This package is designed for calculating syntactic complexity measures on 
the basis of morphosyntactically annotated texts in
[CoNLL-U format](https://universaldependencies.org/format.html).
It also enables sentence segmentation (T-unit and clause extraction) and NP 
extraction.

**Disclaimer**: correct results are only guaranteed for texts annotated with
[UDPipe 2.12](https://lindat.mff.cuni.cz/services/udpipe/api-reference.php).
Please note that syntaxcomp relies heavily on
[CoNLL-U Parser](https://pypi.org/project/conllu/).

## Installation
```bash
pip install syntaxcomp
```

## Usage Example
```python
>>> from syntaxcomp.complexity import SentenceComplexity, TextComplexity

>>> example = """
# udpipe_model = english-ewt-ud-2.12-230717
# sent_id = 1
# text = This is a text containing two sentences.
1	This	this	PRON	DT	Number=Sing|PronType=Dem	4	nsubj	_	_
2	is	be	AUX	VBZ	Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin	4	cop	_	_
3	a	a	DET	DT	Definite=Ind|PronType=Art	4	det	_	_
4	text	text	NOUN	NN	Number=Sing	0	root	_	_
5	containing	contain	VERB	VBG	VerbForm=Ger	4	acl	_	_
6	two	two	NUM	CD	NumForm=Word|NumType=Card	7	nummod	_	_
7	sentences	sentence	NOUN	NNS	Number=Plur	5	obj	_	SpaceAfter=No
8	.	.	PUNCT	.	_	4	punct	_	_

# sent_id = 2
# text = This is the second sentence.
1	This	this	PRON	DT	Number=Sing|PronType=Dem	5	nsubj	_	_
2	is	be	AUX	VBZ	Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin	5	cop	_	_
3	the	the	DET	DT	Definite=Def|PronType=Art	5	det	_	_
4	second	second	ADJ	JJ	Degree=Pos|NumType=Ord	5	amod	_	_
5	sentence	sentence	NOUN	NN	Number=Sing	0	root	_	SpaceAfter=No
6	.	.	PUNCT	.	_	5	punct	_	SpaceAfter=No
"""

>>> tc = TextComplexity(example)
>>> tc.info()
Number of Sentences: 2
Number of Words: 12
Number of Clauses: 3
Number of T-Units: 2
Mean Sentence Length: 6.0
Mean Clause Length: 4.0
Mean T-Unit Length: 6.0
Mean Number of Clauses per Sentence: 1.5
Mean Number of Clauses per T-Unit: 1.5
Mean Tree Depth: 3
Median Tree Depth: 3.0
Minimum Tree Depth: 2
Maximum Tree Depth: 4
Mean Dependency Distance: 2.42
Node-to-Terminal-Node Ratio: 1.5
Average Levenshtein Distance between POS: 3
Average Levenshtein Distance between deprel: 4
Average NP Length: 1.8
Complex NP Ratio: 0.6
Number of Combined Clauses: 1
Number of Coordinate Clauses: 0
Number of Subordinate Clauses: 1
Coordinate to Combined Clause Ratio: 0.0
Subordinate to Combined Clause Ratio: 1.0
Coordinate to Subordinate Clause Ratio: 0.0
Coordinate Clause to Sentence Ratio: 0.0
Subordinate Clause to Sentence Ratio: 0.5
Percentage of root Clauses: 67.0%
Percentage of acl Clauses: 33.0%
```

Alternatively, you can directly pass the result of *conllu.parse* as input:
```python
>>> from conllu import parse
>>> anno = parse(example)
>>> tc = TextComplexity(anno)
```
For SentenceComplexity, *conllu.models.TokenList* is currently the only 
accepted input:
```python
>>> sc = SentenceComplexity(anno[0])
>>> sc.info()
Number of Words: 7
Number of Clauses: 2
Clauses: ['This is a text', 'containing two sentences']
Number of T-Units: 1
T-Units: ['This is a text containing two sentences']
Number of NPs: 3
NPs: ['This', 'a text', 'two sentences']
Tree Depth: 4
Mean Dependency Distance: 2
POS Chain: ['PRON', 'AUX', 'DET', 'NOUN', 'VERB', 'NUM', 'NOUN']
deprel Chain: ['nsubj', 'cop', 'det', 'root', 'acl', 'nummod', 'obj']
```

To display the text and the dependency tree, pass *verbose=True* (for 
TextComplexity, only the text will be printed):
```python
>>> SentenceComplexity(anno[0], verbose=True)
This is a text containing two sentences.
(deprel:root) form:text lemma:text upos:NOUN [4]
    (deprel:nsubj) form:This lemma:this upos:PRON [1]
    (deprel:cop) form:is lemma:be upos:AUX [2]
    (deprel:det) form:a lemma:a upos:DET [3]
    (deprel:acl) form:containing lemma:contain upos:VERB [5]
        (deprel:obj) form:sentences lemma:sentence upos:NOUN [7]
            (deprel:nummod) form:two lemma:two upos:NUM [6]
    (deprel:punct) form:. lemma:. upos:PUNCT [8]
```
