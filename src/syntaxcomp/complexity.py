"""
Get CoNLL-U annotations and calculate syntactic complexity measures.
"""

from __future__ import annotations
from typing import Any
from statistics import mean, median, StatisticsError
from itertools import combinations

import conllu
from conllu import parse
from textdistance import levenshtein


class SentenceComplexity:
    """
    Calculates complexity measures for one sentence.
    """
    def __init__(self, tokenlist: conllu.models.TokenList,
                 verbose: bool = False):
        """
        Calculate sentence-level measures, extract clauses, T-units, etc.
        :param tokenlist: TokenList
        :param verbose: if True, the text and dependency tree will be displayed
        """
        if not isinstance(tokenlist, conllu.models.TokenList):
            raise TypeError(
                'Parameter tokenlist must be conllu.models.TokenList!')

        self.tokenlist = tokenlist
        self.tree = tokenlist.to_tree()
        self.text = tokenlist.metadata['text']
        if verbose:
            print(self.text)
            self.tree.print_tree()

        self.length = 0
        self.c_heads, self.t_heads, self.np_heads = [], [], []
        self.pos_chain, self.dep_chain, self.dep_dists = [], [], []
        nodes, nonterminal = [], []

        for token in self.tokenlist:
            if token['upos'] not in {'PUNCT', 'SYM', '_'}:
                self.length += 1
                # terminal and non-terminal nodes
                nodes.append(token['id'])
                nonterminal.append(token['head'])
                # pos/deprel chains
                self.pos_chain.append(token['upos'])
                self.dep_chain.append(token['deprel'])
                # dependency distances
                self.dep_dists.append(abs(token['head'] - token['id']))
                # T-unit extraction
                if (token['deprel'] in {'root', 'parataxis'} or
                        (token['deprel'] == 'conj' and
                         token['upos'] == 'VERB')):
                    self.t_heads.append(token['id'])
                    self.c_heads.append(token['id'])
                # clause extraction
                elif token['deprel'] in {
                    'advcl', 'advcl:relcl', 'acl', 'acl:relcl', 'ccomp',
                    'nsubj:outer', 'csubj:outer', 'csubj'} or (
                        token['deprel'] == 'xcomp' and token['upos'] == 'VERB'):
                    self.c_heads.append(token['id'])
                # NP extraction
                if token['upos'] in {'NOUN', 'PROPN', 'PRON'}:
                    self.np_heads.append(token['id'])

        self.all_nodes = set(nodes)
        self.nonterminal = set(nonterminal)
        self.terminal = self.all_nodes.difference(self.nonterminal)

        # extract clauses
        self.clauses = self.get_units(self.c_heads)
        self.num_cl = len(self.clauses)
        # extract t-units
        self.t_units = self.get_units(self.t_heads)
        self.num_tu = len(self.t_units)
        # extract NPs
        self.nps = self.get_nps()
        self.num_np = len(self.nps)
        # extract tree depth
        self.tree_depth = self.get_tree_depth(self.tree)

    def __len__(self) -> int:
        """
        Redefine length as the number of non-punctuation tokens in the sentence.
        :return: number of tokens (except PUNCT, SYM, _)
        """
        return self.length

    def get_tree_depth(self, root: conllu.models.TokenTree) -> int:
        """
        Get depth of sentence (number of nodes between the root and its farthest
        descendant).
        :param root: root of the tree
        :return: depth of the sentence, int
        """
        if not root.children:
            return 1
        return 1 + max(self.get_tree_depth(child) for child in root.children)

    def get_curr_node(self, root: conllu.models.TokenTree, curr_id: int):
        """
        Get current node as conllu.models.Token.
        :param root: root of the tree
        :param curr_id: id of the current token
        :return: current node as conllu.models.Token instance
        """
        if root.token['id'] == curr_id:
            return root
        for child in root.children:
            curr_id = self.get_curr_node(child, curr_id)
        return curr_id

    @staticmethod
    def get_descendants(curr_token: conllu.models.TokenTree,
                        heads: list[int]) -> list[int]:
        """
        Recursively get all descendants of a token.
        :param curr_token: current token
        :param heads: heads that must not be included in the descendants
        :return: list of the descendants' ids
        """
        descendants = []

        def recurse(curr_token: conllu.models.TokenTree):
            """
            Recurse through a token's children.
            :param curr_token: current token
            :return: None (appends to list)
            """
            for child in curr_token.children:
                if (child.token['id'] not in heads and
                        child.token['upos'] not in {'_', 'PUNCT', 'SYM'}):
                    descendants.append(child.token['id'])
                    recurse(child)

        recurse(curr_token)
        return descendants

    @staticmethod
    def get_noun_descendants(curr_token: conllu.models.TokenTree) -> list[int]:
        """
        Collects tokens that depend on nouns.
        :param curr_token: current token
        :return: list of noun descendants' ids
        """
        descendants = []

        def recurse(curr_token: conllu.models.TokenTree):
            """
            Recurse through a token's children, collecting tokens that depend on
            nouns.
            :param curr_token: current token
            :return: None (appends to list)
            """
            for child in curr_token.children:
                if (child.token['upos'] not in {'_', 'PUNCT', 'SYM'} and
                        child.token['deprel'] in {
                            'nmod', 'nmod:poss', 'nmod:tmod', 'appos', 'amod',
                            'nummod', 'nummod:gov', 'det', 'case'}):
                    descendants.append(child.token['id'])
                    recurse(child)

        recurse(curr_token)
        return descendants

    def get_units(self, heads: list[int]) -> list[dict[str, Any]]:
        """
        Collect clauses / T-units based on clause / T-unit heads.
        :param heads: ids of clause / T-unit heads
        :return: list of dicts with clause / T-unit information
        """
        units = []
        for head_id in heads:
            head_node = self.get_curr_node(self.tree, head_id)
            descendants = [self.tokenlist.filter(id=child_id)[0]
                           for child_id in self.get_descendants(head_node,
                                                                heads)]
            id_to_text = {head_id: head_node.token['form']}
            for dep in descendants:
                id_to_text[dep['id']] = dep['form']
            unit = {'head_id': head_id,
                    # 'head_node': head_node,
                    'dep_ids': [dep['id'] for dep in descendants],
                    # 'dep_nodes': descendants,
                    'rel_type': head_node.token['deprel'],
                    'text': ' '.join(dict(sorted(id_to_text.items())).values())}
            units.append(unit)
        return units

    def get_nps(self) -> list[dict[str, Any]]:
        """
        Extract noun phrases.
        :return: list of dicts with NP information
        """
        nps = []
        all_descendants = []
        for head_id in self.np_heads:
            head_node = self.get_curr_node(self.tree, head_id)
            descendants = [
                self.tokenlist.filter(id=child_id)[0]
                for child_id in self.get_noun_descendants(head_node)]
            if head_id in all_descendants:
                continue
            all_descendants.extend([dep['id'] for dep in descendants])
            id_to_text = {head_id: head_node.token['form']}
            for dep in descendants:
                id_to_text[dep['id']] = dep['form']
            np = {'head_id': head_id,
                  # 'head_node': head_node,
                  'dep_ids': [dep['id'] for dep in descendants],
                  # 'dep_nodes': descendants,
                  'rel_type': head_node.token['deprel'],
                  'length': len(id_to_text),
                  'text': ' '.join(dict(sorted(id_to_text.items())).values())}
            nps.append(np)
        return nps

    def info(self):
        """
        Prints main sentence complexity features in a convenient format.
        :return: None
        """
        attrs = {'Number of Words': len(self),
                 'Number of Clauses': self.num_cl,
                 'Clauses': [cl['text'] for cl in self.clauses],
                 'Number of T-Units': self.num_tu,
                 'T-Units': [tu['text'] for tu in self.t_units],
                 'Number of NPs': self.num_np,
                 'NPs': [np['text'] for np in self.nps],
                 'Tree Depth': self.tree_depth,
                 'Mean Dependency Distance': round(mean(self.dep_dists), 2),
                 'POS Chain': self.pos_chain,
                 'deprel Chain': self.dep_chain}
        for key, value in attrs.items():
            print(f'{key}: {value}')


class TextComplexity:
    """
    Calculates complexity measures for a text.
    """
    def __init__(self, annotation: str | conllu.models.SentenceList,
                 verbose: bool = False):
        """
        Initialize TextComplexity and SentenceComplexity instances; calculate
        text complexity measures based on sentence statistics.
        :param annotation: CoNLL-U annotation (as string or SentenceList)
        :param verbose: if True, print text
        """
        if isinstance(annotation, str):
            self.sentences = parse(annotation)
        elif isinstance(annotation, conllu.models.SentenceList):
            self.sentences = annotation
        else:
            raise TypeError('Input must be either a string in CoNLL-U format ' +
                            'or a conllu.models.SentenceList!')

        self.text = ' '.join([sent.metadata['text'] for sent in self.sentences])
        if verbose:
            print(self.text)

        self.sent_comp = []
        self.num_w, self.num_cl, self.num_tu = 0, 0, 0
        pos_chains, dep_chains, tree_depths = [], [], []
        dep_dists, terminal, all_nodes, nps = [], [], [], []
        self.clause_counter = dict.fromkeys(
            ['root', 'acl', 'acl:relcl', 'advcl', 'advcl:relcl', 'ccomp',
             'csubj', 'csubj:outer', 'nsubj:outer', 'parataxis', 'xcomp',
             'conj'], 0)

        for sentence in self.sentences:
            # initialize SentenceComplexity instances
            sent = SentenceComplexity(sentence)
            if len(sent) == 0:  # exclude broken sentences
                continue
            self.sent_comp.append(sent)
            self.num_w += len(sent)  # number of words
            self.num_cl += sent.num_cl  # number of clauses
            self.num_tu += sent.num_tu  # number of T-units
            dep_dists.extend(sent.dep_dists)  # dependency distances
            terminal.extend(sent.terminal)  # terminal nodes
            all_nodes.extend(sent.all_nodes)  # all nodes
            nps.extend(sent.nps)  # noun phrases
            pos_chains.append(sent.pos_chain)
            dep_chains.append(sent.dep_chain)
            tree_depths.append(sent.tree_depth)
            for clause in sent.clauses:
                self.clause_counter[clause['rel_type']] += 1

        if self.num_w == 0:
            raise ValueError('The annotation is empty!')

        self.num_s = len(self.sent_comp)  # number of sentences
        self.msl = self.num_w / self.num_s  # mean sentence length
        self.mcl = self.num_w / self.num_cl  # mean clause length
        self.mtl = self.num_w / self.num_tu  # mean t-unit length
        self.cps = self.num_cl / self.num_s  # clauses per sentence
        self.cpt = self.num_cl / self.num_tu  # clauses per T-unit
        self.clause_percentage = {rel: num / self.num_cl
                                  for rel, num in self.clause_counter.items()}

        try:
            # avg Levenshtein distance for POS
            self.lev_pos = mean(self.pairwise_levenshtein(pos_chains))
        except StatisticsError:
            self.lev_pos = 0
        try:
            # avg Levenshtein distance for deprel
            self.lev_dep = mean(self.pairwise_levenshtein(dep_chains))
        except StatisticsError:
            self.lev_dep = 0

        self.mtd = mean(tree_depths)  # mean tree depth
        self.mdtd = median(tree_depths)  # median tree depth
        self.mxtd = max(tree_depths)  # max tree depth
        self.mntd = min(tree_depths)  # min tree depth
        self.mdd = mean(dep_dists)  # mean dependency distance
        self.node_to_term = (len(all_nodes) /
                             len(terminal))  # node to terminal node ratio

        # coordination/subordination measures
        self.comb = self.num_cl - self.num_s  # combined clauses
        self.coord = (self.clause_counter['conj'] +
                      self.clause_counter['parataxis'])
        self.subord = self.comb - self.coord

        try:
            # coordinate to combined clause ratio
            self.coord_to_comb = self.coord / self.comb
        except ZeroDivisionError:
            self.coord_to_comb = 0

        try:
            # subordinate to combined clause ratio
            self.subord_to_comb = self.subord / self.comb
        except ZeroDivisionError:
            self.subord_to_comb = 0

        try:
            # coordinate to subordinate clause ratio
            self.coord_to_subord = self.coord / self.subord
        except ZeroDivisionError:
            self.coord_to_subord = 0

        # coordinate clause to sentence ratio
        self.coord_to_sent = self.coord / self.num_s
        # subordinate clause to sentence ratio
        self.subord_to_sent = self.subord / self.num_s
        # average NP length
        self.avg_np_len = mean([np['length'] for np in nps])
        # complex NPs per clause
        self.comp_np_ratio = len([np for np in nps
                                  if np['length'] > 1]) / len(nps)

    @staticmethod
    def pairwise_levenshtein(chains: list[list[str]]) -> list[int]:
        """
        Calculates pairwise Levenshtein distances between lists of strings.
        :param chains: list of strings
        :return: list of Levenshtein distances between all pairs of lists
        """
        return [levenshtein.distance(a, b) for a, b in combinations(chains, 2)]

    def info(self):
        """
        Prints main text complexity features in a convenient format.
        :return: None
        """
        attrs = {'Number of Sentences': self.num_s,
                 'Number of Words': self.num_w,
                 'Number of Clauses': self.num_cl,
                 'Number of T-Units': self.num_tu,
                 'Mean Sentence Length': round(self.msl, 2),
                 'Mean Clause Length': round(self.mcl, 2),
                 'Mean T-Unit Length': round(self.mtl, 2),
                 'Mean Number of Clauses per Sentence': round(self.cps, 2),
                 'Mean Number of Clauses per T-Unit': round(self.cpt, 2),
                 'Mean Tree Depth': round(self.mtd, 2),
                 'Median Tree Depth': self.mdtd,
                 'Minimum Tree Depth': self.mntd,
                 'Maximum Tree Depth': self.mxtd,
                 'Mean Dependency Distance': round(self.mdd, 2),
                 'Node-to-Terminal-Node Ratio': round(self.node_to_term, 2),
                 'Average Levenshtein Distance between POS': round(
                     self.lev_pos, 2),
                 'Average Levenshtein Distance between deprel':
                     round(self.lev_dep, 2),
                 'Average NP Length': round(self.avg_np_len, 2),
                 'Complex NP Ratio': round(self.comp_np_ratio, 2),
                 'Number of Combined Clauses': self.comb,
                 'Number of Coordinate Clauses': self.coord,
                 'Number of Subordinate Clauses': self.subord,
                 'Coordinate to Combined Clause Ratio':
                     round(self.coord_to_comb, 2),
                 'Subordinate to Combined Clause Ratio':
                     round(self.subord_to_comb, 2),
                 'Coordinate to Subordinate Clause Ratio':
                     round(self.coord_to_subord, 2),
                 'Coordinate Clause to Sentence Ratio':
                     round(self.coord_to_sent, 2),
                 'Subordinate Clause to Sentence Ratio':
                     round(self.subord_to_sent, 2)}
        for key, val in attrs.items():
            print(f'{key}: {val}')
        for deprel, percentage in self.clause_percentage.items():
            if percentage > 0:
                print(f'Percentage of {deprel} Clauses: '
                      f'{round(percentage * 100, 0)}%')
