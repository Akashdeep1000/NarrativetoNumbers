from __future__ import annotations

def plan_for_seed(seed: int):
    base = ['A','B','C','D']
    rot = seed % 4
    order = base[rot:] + base[:rot]
    mapping = {'A':'easy','B':'hard','C':'easy','D':'hard'}
    return [{'index': i+1, 'condition': c, 'difficulty': mapping[c], 'shuffle_steps': (25 if mapping[c]=='easy' else 100)} for i, c in enumerate(order)]
