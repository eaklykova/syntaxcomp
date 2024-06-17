from statistics import mean, median, StatisticsError
from itertools import combinations
from textdistance import levenshtein

import conllu
from conllu import parse


class SentenceComplexity:

    def __init__(self, tokenlist, tree, verbose=False):
        self.tokenlist = tokenlist
        self.tree = tree
        self.text = tokenlist.metadata['text']
        if verbose:
            tree.print_tree()

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

        self.nonterminal = set(nonterminal)
        self.terminal = set(nodes).difference(self.nonterminal)

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

    def __len__(self):
        return self.length

    def get_tree_depth(self, root):
        if not root.children:
            return 1
        else:
            return 1 + max(self.get_tree_depth(child)
                           for child in root.children)

    def get_curr_node(self, root, curr_id):
        if root.token['id'] == curr_id:
            return root
        for child in root.children:
            curr_id = self.get_curr_node(child, curr_id)
        return curr_id

    @staticmethod
    def get_descendants(curr_token, heads):
        descendants = []

        def recurse(curr_token):
            for child in curr_token.children:
                if (child.token['id'] not in heads and
                        child.token['upos'] not in {'_', 'PUNCT', 'SYM'}):
                    descendants.append(child.token['id'])
                    recurse(child)

        recurse(curr_token)
        return descendants

    @staticmethod
    def get_noun_descendants(curr_token):
        descendants = []

        def recurse(curr_token):
            for child in curr_token.children:
                if (child.token['upos'] not in {'_', 'PUNCT', 'SYM'} and
                        child.token['deprel'] in {
                            'nmod', 'nmod:poss', 'nmod:tmod', 'appos', 'amod',
                            'nummod', 'nummod:gov', 'det', 'case'}):
                    descendants.append(child.token['id'])
                    recurse(child)
        recurse(curr_token)

        return descendants

    def get_units(self, heads):
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
                    'head_node': head_node,
                    'dep_ids': [dep['id'] for dep in descendants],
                    'dep_nodes': descendants,
                    'rel_type': head_node.token['deprel'],
                    'text': ' '.join(dict(sorted(id_to_text.items())).values())}
            units.append(unit)
        return units

    def get_nps(self):
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
                  'head_node': head_node,
                  'dep_ids': [dep['id'] for dep in descendants],
                  'dep_nodes': descendants,
                  'rel_type': head_node.token['deprel'],
                  'length': len(id_to_text),
                  'text': ' '.join(dict(sorted(id_to_text.items())).values())}
            nps.append(np)
        return nps


class TextComplexity:

    def __init__(self, annotation):

        if isinstance(annotation, str):
            self.sentences = parse(annotation)
            self.trees = [sent.to_tree() for sent in self.sentences]
        elif isinstance(annotation, conllu.models.SentenceList):
            self.sentences = annotation
            self.trees = [sent.to_tree() for sent in annotation]
        else:
            raise TypeError('Input must be either a string in CoNLL-U format ' +
                            'or a conllu.models.SentenceList!')

        # initialize SentenceComplexity instances
        self.sent_comp = []
        self.num_w, self.num_cl, self.num_tu = 0, 0, 0
        self.pos_chains, self.dep_chains, self.tree_depths = [], [], []
        dep_dists, terminal, nonterminal, nps = [], [], [], []
        self.clause_counter = dict.fromkeys(
            ['root', 'acl', 'acl:relcl', 'advcl', 'advcl:relcl', 'ccomp',
             'csubj', 'csubj:outer', 'nsubj:outer', 'parataxis', 'xcomp',
             'conj'], 0)

        for i, sent in enumerate(self.sentences):
            sent = SentenceComplexity(sent, self.trees[i])
            self.sent_comp.append(sent)
            if len(sent) == 0:  # exclude broken sentences
                continue
            self.num_w += len(sent)  # number of words
            dep_dists.extend(sent.dep_dists)  # dependency distances
            terminal.extend(sent.terminal)  # terminal nodes
            nonterminal.extend(sent.nonterminal)  # nonterminal nodes
            nps.extend(sent.nps)  # noun phrases
            self.num_cl += sent.num_cl
            self.num_tu += sent.num_tu
            self.pos_chains.append(sent.pos_chain)
            self.dep_chains.append(sent.dep_chain)
            self.tree_depths.append(sent.tree_depth)
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

        try:
            # avg Levenshtein distance for POS
            self.lev_pos = mean(self.pairwise_levenshtein(self.pos_chains))
        except StatisticsError:
            self.lev_pos = 0
        try:
            # avg Levenshtein distance for deprel
            self.lev_dep = mean(self.pairwise_levenshtein(self.dep_chains))
        except StatisticsError:
            self.lev_dep = 0

        self.mtd = mean(self.tree_depths)  # mean tree depth
        self.mdtd = median(self.tree_depths)  # median tree depth
        self.mxtd = max(self.tree_depths)  # max tree depth
        self.mntd = min(self.tree_depths)  # min tree depth
        self.mdd = mean(dep_dists)  # mean dependency distance
        self.node_to_term = (len(nonterminal) /
                             len(terminal))  # node to terminal node ratio

        # clausal measures
        self.clause_percentage = {rel: num / self.num_cl
                                  for rel, num in self.clause_counter.items()}

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
    def pairwise_levenshtein(chains):
        return [levenshtein.distance(a, b) for a, b in combinations(chains, 2)]
