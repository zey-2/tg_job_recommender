from database import Database
from keyword_manager import KeywordManager
import tempfile, os

fn = tempfile.NamedTemporaryFile(delete=False).name
print('DB path:', fn)

# Initialize DB
db = Database(db_path=fn)
# Create test user
if not db.get_user(555):
    db.create_user(555, 'tester')

# Add manual keywords
manual = ['python','data','ml','pandas']
for kw in manual:
    db.upsert_keyword(555, kw, 1.0, is_negative=False, rationale='manual test', source='manual')

# Add auto keywords
autos = [('skill1', 0.8), ('skill2', 0.7), ('skill3', 0.6), ('skill4', 0.5), ('skill5', 0.4)]
for kw, w in autos:
    db.upsert_keyword(555, kw, w, is_negative=False, rationale='auto test', source='auto')

print('Initial keywords:')
for k in db.get_user_keywords(555):
    print(k)

# Apply decay (should not affect manual)
db.decay_keywords(555, 0.5)
print('\nAfter decay:')
for k in db.get_user_keywords(555):
    print(k)

# Prune so we keep max 4 manual + 4 auto (TOP_K=8, MAX_MANUAL_KEYWORDS=4)
km = KeywordManager()
# monkeypatch LLM to avoid external call
km.llm.expand_keywords = lambda **kwargs: []
km._prune_keywords(555)

print('\nAfter prune:')
for k in db.get_user_keywords(555):
    print(k)

# Test update_keywords_from_feedback - ensure manual keyword weight not increased
job = {'title': 'Python Developer', 'description': 'Worked with python and pandas', 'company': 'Company X'}
# Get weight before
before = next((kw for kw in db.get_user_keywords(555) if kw['keyword'] == 'python'), None)
print('\nBefore like on job, python weight:', before['weight'])
km.update_keywords_from_feedback(555, job, 'like')
after = next((kw for kw in db.get_user_keywords(555) if kw['keyword'] == 'python'), None)
print('After like on job, python weight:', after['weight'])

# Print final list
print('\nFinal keywords:')
for k in db.get_user_keywords(555):
    print(k)

# Cleanup
os.unlink(fn)