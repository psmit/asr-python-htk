

PROTO = """~o <VecSize> 39 <MFCC_0_D_A_Z>
~h "proto"
<BeginHMM>
        <NumStates> 5
        <State> 2
                <Mean> 39
0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0
                <Variance> 39
1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0
        <State> 3
                <Mean> 39
0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0
                <Variance> 39
1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0
        <State> 4
                <Mean> 39
0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0
                <Variance> 39
                1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0
<TransP> 5
0.0 1.0 0.0 0.0 0.0
0.0 0.6 0.4 0.0 0.0
0.0 0.0 0.6 0.4 0.0
0.0 0.0 0.0 0.7 0.3
0.0 0.0 0.0 0.0 0.0
<EndHMM>"""

MKMONO = """EX
IS sil sil"""

TRANSP3 = """<TRANSP> 3
 0.000000e+00 5.000000e-01 5.000000e-01
 0.000000e+00 5.000000e-01 5.000000e-01
 0.000000e+00 0.000000e+00 0.000000e+00
<ENDHMM>"""

SIL_HED = """AT 2 4 0.2 {sil.transP}
AT 4 2 0.2 {sil.transP}
AT 1 3 0.3 {sp.transP}
TI silst {sil.state[3],sp.state[2]}
"""

MKTRI = """ME sil sil sil
WB sp
NB sp
TC sil sil"""


GLOBAL = """~b "{global_name:>s}"
        <MMFIDMASK> *
        <PARAMETERS> MIXBASE
        <NUMCLASSES> 1
        <CLASS> 1 {{*.state[2-4].mix[1-1000]}}"""

# RN "{global_name:>s}" removed
REGTREE_HED = """LS "{stats_file:>s}"
RC {num_nodes:d} "{regtree:>s}" """

BASE_ADAP_CONFIG = """HADAPT:BASECLASS = {base_class:>s}
HADAPT:USEBIAS = TRUE
HADAPT:TRANSKIND = CMLLR"""

# HADAPT:BASECLASS = {base_class:>s} removed
TREE_ADAP_CONFIG = """HADAPT:USEBIAS = TRUE
HADAPT:TRANSKIND = CMLLR
HADAPT:ADAPTKIND = TREE
HADAPT:REGTREE = {regtree:>s}"""


HVITE_CONFIG = """
FORCECXTEXP = T
ALLOWXWRDEXP = T"""