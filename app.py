"""
OPEN-REDACTOR - Web Interface
"""

from flask import Flask, request, render_template_string, jsonify
from transformers import pipeline
import re

app = Flask(__name__)

# Load model once
print("🔄 Loading AI model...")
ner = pipeline("ner", model="dslim/bert-base-NER", aggregation_strategy="simple")
print("✅ Model loaded!")

def redact_text(text):
    patterns = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'credit_card': r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'
    }
    
    entities = []
    for name, pattern in patterns.items():
        for match in re.finditer(pattern, text):
            entities.append({
                'type': name,
                'value': match.group(),
                'start': match.start(),
                'end': match.end()
            })
    
    ai_results = ner(text)
    type_map = {'PER': 'person_name', 'LOC': 'location', 'ORG': 'organization'}
    for entity in ai_results:
        entities.append({
            'type': type_map.get(entity['entity_group'], entity['entity_group']),
            'value': entity['word'],
            'start': entity['start'],
            'end': entity['end']
        })
    
    seen = set()
    unique = []
    for e in entities:
        key = (e['start'], e['end'])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    
    unique.sort(key=lambda x: x['start'])
    redacted = text
    offset = 0
    for entity in unique:
        start = entity['start'] + offset
        end = entity['end'] + offset
        redacted = redacted[:start] + '[REDACTED]' + redacted[end:]
        offset += len('[REDACTED]') - (end - start)
    
    return redacted, unique


# HTML for the web interface
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Open-Redactor - Real-time PII Redaction</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
        }
        textarea {
            width: 100%;
            height: 150px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
            resize: vertical;
        }
        button {
            background: #007bff;
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin-top: 10px;
        }
        button:hover {
            background: #0056b3;
        }
        .result {
            margin-top: 20px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 5px;
            border-left: 4px solid #28a745;
        }
        .redacted {
            background: #ffeb3b;
            padding: 2px 5px;
            border-radius: 3px;
            font-weight: bold;
        }
        .entities {
            margin-top: 10px;
            padding: 10px;
            background: #fff3cd;
            border-radius: 5px;
        }
        .entity {
            display: inline-block;
            background: #ffc107;
            padding: 3px 10px;
            margin: 3px;
            border-radius: 3px;
            font-size: 12px;
        }
        .badge {
            display: inline-block;
            background: #dc3545;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 12px;
            margin-left: 5px;
        }
        .examples {
            margin: 15px 0;
            padding: 10px;
            background: #e9ecef;
            border-radius: 5px;
        }
        .example-btn {
            background: #6c757d;
            color: white;
            border: none;
            padding: 5px 10px;
            margin: 2px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 12px;
        }
        .example-btn:hover {
            background: #5a6268;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔒 Open-Redactor</h1>
        <p>Real-time PII redaction using open AI models</p>
        
        <div class="examples">
            <strong>Try these examples:</strong><br>
            <button class="example-btn" onclick="fillExample(1)">Person Info</button>
            <button class="example-btn" onclick="fillExample(2)">Financial</button>
            <button class="example-btn" onclick="fillExample(3)">Contact</button>
        </div>
        
        <form method="POST" id="redactForm">
            <textarea name="text" placeholder="Paste text containing personal information...">{{ request.form.text if request.form.text else '' }}</textarea>
            <br>
            <button type="submit">🔐 Redact PII</button>
        </form>
        
        {% if result %}
        <div class="result">
            <h3>📝 Original:</h3>
            <p>{{ request.form.text }}</p>
            
            <h3>🔐 Redacted:</h3>
            <p>{{ result }}</p>
            
            <div class="entities">
                <strong>📊 Found {{ entities|length }} items:</strong>
                {% for entity in entities %}
                <span class="entity">{{ entity.type }}: {{ entity.value }}</span>
                {% endfor %}
            </div>
        </div>
        {% endif %}
    </div>
    
    <script>
        function fillExample(num) {
            const examples = [
                "My name is John Smith. Email: john.smith@email.com. Call me at (555) 123-4567.",
                "Credit card: 1234-5678-9012-3456. SSN: 123-45-6789. Bank: Chase.",
                "Contact Sarah Johnson at sarah.j@company.com or +1 (800) 555-0199."
            ];
            document.querySelector('textarea').value = examples[num-1];
            document.getElementById('redactForm').submit();
        }
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    entities = []
    if request.method == 'POST':
        text = request.form.get('text', '')
        if text:
            result, entities = redact_text(text)
    return render_template_string(HTML, result=result, entities=entities)


@app.route('/api/redact', methods=['POST'])
def api_redact():
    """REST API endpoint for redaction"""
    data = request.get_json()
    text = data.get('text', '')
    result, entities = redact_text(text)
    return jsonify({
        'original': text,
        'redacted': result,
        'entities': entities,
        'count': len(entities)
    })


if __name__ == '__main__':
    print("=" * 60)
    print("🌐 Open-Redactor Web Interface")
    print("=" * 60)
    print("📍 Open in browser: http://localhost:5000")
    print("📍 API endpoint: http://localhost:5000/api/redact")
    print("=" * 60)
    app.run(debug=True)