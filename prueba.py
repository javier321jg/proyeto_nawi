import requests
import json

def test_gemini_api(prompt):
    API_KEY = 'AIzaSyBRIi92h8EEc_TjA227kcbPx6iRyL3vk3k'
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={API_KEY}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    data = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        
        print(f"\n=== Detalles de la solicitud ===")
        print(f"Status Code: {response.status_code}")
        print(f"Tokens: {result.get('usageMetadata', {}).get('promptTokenCount', 'N/A')}")
        
        if response.status_code == 200:
            if 'candidates' in result and result['candidates']:
                candidate = result['candidates'][0]
                
                if 'content' in candidate:
                    text = candidate['content']['parts'][0]['text']
                    print("\n=== Respuesta ===")
                    print(text)
                    
                    # Guardar en archivo
                    with open('gemini_response.txt', 'w', encoding='utf-8') as f:
                        f.write(text)
                    return True, text
                else:
                    print(f"\nRespuesta bloqueada: {candidate.get('finishReason', 'Unknown')}")
                    return False, None
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return False, None

def main():
    # Prompt dividido en partes más pequeñas y generales
    prompts = [
        """Describe general cultivation practices for strawberries:
        1. Optimal growing conditions
        2. Basic care requirements""",
        
        """Explain plant health management:
        1. Common challenges
        2. Prevention methods""",
        
        """Discuss agricultural best practices:
        1. Soil preparation
        2. Irrigation methods""",
        
        """Share information about crop care:
        1. Monitoring techniques
        2. Maintenance tips"""
    ]
    
    print("=== Iniciando consultas ===")
    
    for i, prompt in enumerate(prompts, 1):
        print(f"\nConsulta {i}:")
        success, response = test_gemini_api(prompt)
        
        if success:
            print(f"✓ Consulta {i} exitosa")
        else:
            print(f"✗ Consulta {i} fallida")
        
        # Pequeña pausa entre consultas
        import time
        time.sleep(1)

if __name__ == "__main__":
    main()