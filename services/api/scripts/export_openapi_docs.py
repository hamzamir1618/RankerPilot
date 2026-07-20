import sys
import os
import json

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app

def generate_markdown():
    openapi = app.openapi()
    
    md = ["# RankerPilot API Reference", ""]
    md.append("This document is automatically generated from the OpenAPI specification.")
    md.append("")
    
    # Process paths
    for path, path_item in openapi.get("paths", {}).items():
        for method, operation in path_item.items():
            method_upper = method.upper()
            summary = operation.get("summary", "No summary provided.")
            description = operation.get("description", "No description provided.")
            
            md.append(f"## {method_upper} {path}")
            md.append(f"**{summary}**")
            md.append("")
            md.append(f"{description}")
            md.append("")
            
            # Auth
            security = operation.get("security", [])
            auth_req = "None"
            if security:
                auth_req = ", ".join(list(s.keys())[0] for s in security if s)
            md.append(f"**Authentication:** {auth_req}")
            md.append("")
            
            # Request Body
            req_body = operation.get("requestBody")
            req_example = None
            if req_body:
                content = req_body.get("content", {}).get("application/json", {})
                schema_ref = content.get("schema", {}).get("$ref")
                if schema_ref:
                    schema_name = schema_ref.split("/")[-1]
                    schema = openapi["components"]["schemas"].get(schema_name, {})
                    
                    md.append("### Request Body")
                    md.append("| Field | Type | Required | Description |")
                    md.append("|---|---|---|---|")
                    
                    req_example = {}
                    for prop_name, prop_data in schema.get("properties", {}).items():
                        prop_type = prop_data.get("type", "string")
                        is_required = "Yes" if prop_name in schema.get("required", []) else "No"
                        prop_desc = prop_data.get("description", "")
                        md.append(f"| `{prop_name}` | `{prop_type}` | {is_required} | {prop_desc} |")
                        
                        # Generate example
                        if prop_type == "string":
                            req_example[prop_name] = "string_value"
                        elif prop_type == "integer":
                            req_example[prop_name] = 123
                        elif prop_type == "boolean":
                            req_example[prop_name] = True
                        else:
                            req_example[prop_name] = {}
                    md.append("")
                    
            if req_example:
                md.append("#### Example Request")
                md.append("```json")
                md.append(json.dumps(req_example, indent=2))
                md.append("```")
                md.append("")
                
            # Responses
            md.append("### Responses")
            responses = operation.get("responses", {})
            for status, resp_data in responses.items():
                desc = resp_data.get("description", "")
                md.append(f"- **{status}**: {desc}")
            md.append("")
            
            # Generate Example Response (200)
            success_resp = responses.get("200") or responses.get("201") or responses.get("202")
            if success_resp:
                content = success_resp.get("content", {}).get("application/json", {})
                schema = content.get("schema", {})
                
                example_resp = {}
                if "$ref" in schema:
                    schema_name = schema["$ref"].split("/")[-1]
                    comp_schema = openapi["components"]["schemas"].get(schema_name, {})
                    for prop_name, prop_data in comp_schema.get("properties", {}).items():
                        prop_type = prop_data.get("type", "string")
                        if prop_type == "string":
                            example_resp[prop_name] = "example_string"
                        elif prop_type == "integer":
                            example_resp[prop_name] = 100
                        elif prop_type == "boolean":
                            example_resp[prop_name] = True
                        else:
                            example_resp[prop_name] = {}
                elif schema.get("type") == "array":
                    example_resp = [{"id": "example_id"}]
                    
                md.append("#### Example Success Response")
                md.append("```json")
                md.append(json.dumps(example_resp, indent=2))
                md.append("```")
                md.append("")
                
            # Generate Example Error (400 or 404 or 422)
            error_resp_status = None
            for s in ["400", "401", "402", "403", "404", "409", "422", "429"]:
                if s in responses:
                    error_resp_status = s
                    break
            
            if error_resp_status:
                md.append(f"#### Example Error Response ({error_resp_status})")
                md.append("```json")
                md.append(json.dumps({"detail": "Error description corresponding to the status code."}, indent=2))
                md.append("```")
                md.append("")
                
            md.append("---")
            md.append("")

    # Append Webhook & SSE Documentation
    md.append("## Server-Sent Events (SSE)")
    md.append("`GET /v1/audits/{id}/events`")
    md.append("Streams live audit events.")
    md.append("### Event Types")
    md.append("- `crawl.progress`: Fired when pages are crawled. `{\"url\": \"...\", \"status\": 200}`")
    md.append("- `agent.started`: Fired when an AI agent starts. `{\"agent\": \"...\"}`")
    md.append("- `agent.completed`: Fired when an agent finishes. `{\"agent\": \"...\"}`")
    md.append("- `audit.done`: Fired when the audit is successfully completed.")
    md.append("")
    md.append("## Webhook Payload & Verification")
    md.append("When a webhook is triggered, RankerPilot sends a POST request with the event payload.")
    md.append("### Example Payload")
    md.append("```json")
    md.append('{\n  "event": "audit.completed",\n  "audit_id": "123",\n  "status": "done"\n}')
    md.append("```")
    md.append("### Signature Verification (Python)")
    md.append("```python")
    md.append("import hmac, hashlib")
    md.append("signature = hmac.new(SECRET.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()")
    md.append("if f'sha256={signature}' == request.headers.get('X-Rankerpilot-Signature'):")
    md.append("    print('Valid!')")
    md.append("```")
    md.append("")

    with open(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'docs', 'API.md'), 'w') as f:
        f.write("\n".join(md))
        
if __name__ == "__main__":
    generate_markdown()
    print("Generated docs/API.md")
