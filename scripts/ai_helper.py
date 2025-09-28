# Tạo limiter: 30 req / 60s
import os
from typing import List

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json
from my_type import CHOOSEN_MODEL, GEMINI_MODEL, GROQ_MODEL, Dream, RateLimiter

from google import genai
from google.genai import types

from output_helper import write_output

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())  # loads .env into process env

_rate_limiter_30_per_min = RateLimiter(30, 60.0) # gemini-2.0-flash-lite

# Tạo limiter: 15 req / 60s
_rate_limiter_15_per_min = RateLimiter(15, 60.0) # gemini-2.5-flash-lite

# Tạo limiter: 10 req / 60s
_rate_limiter_10_per_min = RateLimiter(10, 60.0) # gemini-2.5-flash

# if CHOOSEN_MODEL == GEMINI_MODEL.GEMINI_2_5_FLASH:
#     _rate_limiter_10_per_min.acquire()
# if CHOOSEN_MODEL == GEMINI_MODEL.GEMINI_2_0_FLASH_LITE:
#     _rate_limiter_30_per_min.acquire()
# if CHOOSEN_MODEL == GEMINI_MODEL.GEMINI_2_5_FLASH_LITE or CHOOSEN_MODEL == GEMINI_MODEL.GEMINI_2_0_FLASH:
#     _rate_limiter_15_per_min.acquire()
  
def gemini_prompt(prompt: str, OUTPUT_FILENAME: str, model: GEMINI_MODEL):    
    _rate_limiter_10_per_min.acquire()
      
    system_instruction = """
    công việc của bạn là nhận dữ liệu text được đọc từ 1 file pdf (nội dung của pdf chủ yếu là về những giấc mơ), 
    và bạn có nhiệm vụ phải chắt lọc lấy đúng phần nội dung của giấc mơ trong đoạn text đó, với các yêu cầu sau:
    - tôi muốn trả về 1 mảng JSON (no prose) gồm các giấc mơ có trong đoạn text trên, 
    1 giấc mơ có 6 key case_id, dream_id, date, dream_text, state_of_mind, notes, 
    với case_id có format là Cxxxx (x là số, ví dụ C0001, C0002,...) và phải bắt đầu từ case_id trước đó (được cung cấp trong văn bản),
    tất cả các giấc mơ trong cùng 1 đoạn text đều có chung case_id, state_of_mind (được lấy từ cụm từ "State of mind: " hoặc  "Dream mood:" trong văn bản) và
    date (lấy theo định dạng dd/mm/yyyy),
    notes là From PDF: title_pdf, 
    dream_id có format là Dxxxx (x là số, ví dụ D0001, D0002,...),
    phần dream_text là quan trọng nhất, bạn phải lấy chính xác từng dream riêng biệt,
    và nội dung phải y hệt với văn bản gốc (loại bỏ các ký tự escapse, các từ để liệt kê như my first dream is, second dream,... hay các chỉ mục 1., 2., ...),
    """

    client = genai.Client()

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        response_mime_type="application/json",
        response_schema=list[Dream],
    )
    
    response = client.models.generate_content(
        model=model.value, contents=prompt, config=config
    )

    data: List[Dream] = response.parsed
    
    write_output(f"\n{response.text}\n", OUTPUT_FILENAME)
    
    return data

def groq_prompt(user_prompt: str, OUTPUT_FILENAME: str, model: GROQ_MODEL, pdf_title: str = "Unknown PDF"): 
    # rateLimiter = RateLimiter(40, 60.0) # gemini-2.0-flash-lite
    # rateLimiter.acquire()

    
    # Initialize Groq LLM
    llm = ChatGroq(
        model_name=model.value,
        temperature=0
    )

    
    # Tell the parser exactly what JSON we want
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["case_id", "dream_id", "date", "dream_text", "state_of_mind", "notes"],
            "properties": {
                "case_id": {"type": "string"},
                "dream_id": {"type": "string"},
                "date": {"type": "string", "description": "format dd/mm/yyyy when possible"},
                "dream_text": {"type": "string"},
                "state_of_mind": {"type": "string"},
                "notes": {"type": "string"}
            },
            "additionalProperties": False
        }
    }
    parser = JsonOutputParser(schema=schema)
    format_instructions = parser.get_format_instructions()

    # Build a clean, variable-safe system message.
    # IMPORTANT: no quoted placeholder names like {'case_id'}; use {case_id} only when you intend variables.
    base_instruction = (
        "Extract each distinct dream report from the user's text. "
        "Output ONLY JSON and always in JSON Array (no prose). Each item must include these fields: "
        "case_id, dream_id, date, dream_text, state_of_mind, notes. "
        f"and when generating dream_id, continue from last_dream_id (in text) and use 4 digits (e.g., D0001, D0002...). "
        "case_id is C01 for all dreams. "
        "All dreams share the same state_of_mind, state_of_mind is after this word: 'State of mind: '."
        "All dreams share the same date, format date to dd/mm/yyyy format."
        f'set notes to "From PDF: {pdf_title}" .'
        "If a field is unknown, use an empty string."
    )
    sys_msg = f"{base_instruction.strip()}"
    # sys_msg = f"{instruction.strip()}\n\n{base_instruction}" if instruction else base_instruction


    prompt = ChatPromptTemplate.from_messages([
        ("system", "{sys_msg}\n\n{format_instructions}"),
        ("user",
         "Context:\n"
         "pdf_title: {pdf_title}\n"
         "Text:\n{input}")
    ])

    # Chain: prompt -> LLM -> JSON parser
    chain = prompt | llm | parser

    # Invoke with all required variables
    result = chain.invoke({
        "sys_msg": sys_msg,
        "format_instructions": format_instructions,
        "pdf_title": pdf_title,
        "input": user_prompt,
    })
    
    write_output(f"\n{result}\n", OUTPUT_FILENAME)

    result = [Dream(**d) for d in result]

    return result