from conllu import parse
from complexity import TextComplexity, SentenceComplexity

anno = '''
# generator = UDPipe 2, https://lindat.mff.cuni.cz/services/udpipe
# udpipe_model = english-ewt-ud-2.12-230717
# udpipe_model_licence = CC BY-NC-SA
# newdoc
# newpar
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
'''

con = parse(anno)
tc = TextComplexity(con)  # or simply tc = TextComplexity(anno)
tc.info()

sc = SentenceComplexity(con[0])
sc.info()

SentenceComplexity(con[0], verbose=True)
