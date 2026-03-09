from le_utils.constants.labels import levels
from le_utils.constants.labels import subjects

"""
University = Tertiary
High School = Upper Secondary
Middle School / Elementary 2 = Lower Secondary 
Elementary School = Lower Primary, Upper Primary 
"""

METADATA_BY_SLUG = {
    'elementary school': {'grade_levels': [levels.LOWER_PRIMARY, levels.UPPER_PRIMARY], 'categories': []},
    'basic education': {'grade_levels': [levels.LOWER_PRIMARY, levels.UPPER_PRIMARY], 'categories': []},
    'primary school': {'grade_levels': [levels.LOWER_PRIMARY, levels.UPPER_PRIMARY], 'categories': []},
    'primary school, second grade': {'grade_levels': [levels.LOWER_SECONDARY], 'categories': []},
    'middle school': {'grade_levels': [levels.LOWER_SECONDARY], 'categories': []},
    'lower secondary school': {'grade_levels': [levels.LOWER_SECONDARY], 'categories': []},
    'high school': {'grade_levels': [levels.UPPER_SECONDARY], 'categories': []},
    'secondary school': {'grade_levels': [levels.UPPER_SECONDARY], 'categories': []},
    'upper secondary school': {'grade_levels': [levels.UPPER_SECONDARY], 'categories': []},
    'university': {'grade_levels': [levels.TERTIARY], 'categories': []},
    'college': {'grade_levels': [levels.TERTIARY], 'categories': []},
    'mathconcepts': {'grade_levels': [], 'categories': [subjects.MATHEMATICS]},
    'math concepts': {'grade_levels': [], 'categories': [subjects.MATHEMATICS]},
    'mathematical concepts': {'grade_levels': [], 'categories': [subjects.MATHEMATICS]},
    'mathematics': {'grade_levels': [], 'categories': [subjects.MATHEMATICS]},
    'math apps': {'grade_levels': [], 'categories': [subjects.MATHEMATICS]},
    'applied mathematics': {'grade_levels': [], 'categories': [subjects.MATHEMATICS]},
    'mathapplications': {'grade_levels': [], 'categories': [subjects.MATHEMATICS]},
    'mathematical applications': {'grade_levels': [], 'categories': [subjects.MATHEMATICS]},
    'mathematics concepts': {'grade_levels': [], 'categories': [subjects.MATHEMATICS]},
    'math applications': {'grade_levels': [], 'categories': [subjects.MATHEMATICS]},
    'light & radiation': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'electricity, magnets & circuits': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'biology': {'grade_levels': [], 'categories': [subjects.BIOLOGY]},
    'chemistry': {'grade_levels': [], 'categories': [subjects.CHEMISTRY]},
    'chemical': {'grade_levels': [], 'categories': [subjects.CHEMISTRY]},
    'earth-science': {'grade_levels': [], 'categories': [subjects.EARTH_SCIENCE]},
    'earth science': {'grade_levels': [], 'categories': [subjects.EARTH_SCIENCE]},
    'earth sciences': {'grade_levels': [], 'categories': [subjects.EARTH_SCIENCE]},
    'math': {'grade_levels': [], 'categories': [subjects.MATHEMATICS]},
    'general': {'grade_levels': [], 'categories': [subjects.CHEMISTRY]},
    'physics': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'physical': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'motion': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'sound & waves': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'work-energy-and-power': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'work, energy & power': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'heat-and-thermodynamics': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'quantum-phenomena': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'heat & thermo': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'quantum phenomena': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'University': {'grade_levels': [levels.TERTIARY], 'categories': []}
}
METADATA_BY_CAT = {22: {'grade_levels': [levels.LOWER_PRIMARY, levels.UPPER_PRIMARY] },
                   23: {'grade_levels': [levels.LOWER_SECONDARY]},
                   24: {'grade_levels': [levels.UPPER_SECONDARY]},
                   25:  {'grade_levels': [levels.TERTIARY]},
                   4:  { 'categories': [subjects.PHYSICS]},
                   12: { 'categories': [subjects.BIOLOGY]},
                   13: { 'categories': [subjects.CHEMISTRY]},
                   14:  { 'categories': [subjects.EARTH_SCIENCE]},
                   15:  { 'categories': [subjects.MATHEMATICS]}
                   }

