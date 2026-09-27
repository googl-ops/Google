import os
import streamlit as st
from openai import OpenAI
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import re
import math
import random
import traceback
import pypdf
import io

# جلب المفتاح من Streamlit Secrets
try:
    api_key = st.secrets["GROQ_API_KEY"]
except Exception:
    api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("⚠️ مفتاح Groq API غير مُعد بشكل صحيح في إعدادات المعمل.")
    st.stop()

# تهيئة عميل Groq (متوافق مع OpenAI SDK)
client = OpenAI(
    api_key=api_key.strip(),
    base_url="https://api.groq.com/openai/v1"
)


def extract_text_from_pdf(pdf_file):
    """استخراج النص من ملف PDF."""
    if pdf_file is None:
        return ""
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_file.read()))
        text = ""
        max_pages = min(len(reader.pages), 15)
        for i in range(max_pages):
            page_text = reader.pages[i].extract_text() or ""
            text += f"\n--- صفحة {i+1} ---\n{page_text}"
        return text
    except Exception as e:
        return f"خطأ في قراءة ملف PDF: {str(e)}"


def clean_code(code: str) -> str:
    """تنظيف الكود من أسوار Markdown وإصلاح الخصائص القديمة."""
    code = code.strip()
    code = re.sub(r"^```(?:python)?\s*", "", code)
    code = re.sub(r"\s*```$", "", code)
    # إصلاح تلقائي للخاصية القديمة titlefont
    code = code.replace("titlefont=", "title_font=")
    code = code.replace("titlefont =", "title_font =")
    return code.strip()


def run_universal_lab(exp_text, pdf_file):
    context = ""
    if pdf_file is not None:
        pdf_content = extract_text_from_pdf(pdf_file)
        if pdf_content and not pdf_content.startswith("خطأ"):
            context += f"\n[محتوى من كتاب الفيزياء]:\n{pdf_content}\n"

    if exp_text and exp_text.strip():
        context += f"\n[اسم التجربة / النص]:\n{exp_text}\n"

    if not context.strip():
        st.warning("⚠️ يرجى كتابة اسم التجربة أو رفع ملف كتاب الفيزياء.")
        return None, None

    system_prompt = f"""أنت محرك معمل فيزياء افتراضي محترف ومهندس Python خبير.
بناءً على المدخلات التالية:
{context}

المطلوب منك بدقة:
1. اكتب كود Python كامل وقابل للتنفيذ مباشرة، بدون أي شرح نصي خارج الكود.
2. يجب أن يحتوي الكود على متغير باسم `fig` وهو كائن Plotly (go.Figure)
   يمثل رسمًا بيانيًا تفاعليًا للتجربة مع عناوين عربية ومحاور معنونة.
3. يجب أن يحتوي الكود على متغير نصي باسم `analysis_html` يحتوي على شرح HTML
   أنيق بالعربية (القوانين، الخطوات، النتائج، الاستنتاجات) مع CSS مضمّن.
4. المكتبات المتاحة فقط: numpy (np)، plotly.graph_objects (go)،
   plotly.express (px)، math، random.
5. لا تستخدم matplotlib أو pandas أو أي مكتبة غير مذكورة.
6. لا تستخدم input() ولا أي تفاعل خارجي.
7. أرجع الكود فقط داخل كتلة برمجية ```python ... ```.

مهم جدًا: تأكد أن الكود لن يرمي أي استثناء، واستخدم أرقامًا فيزيائية واقعية.
تحذير هام جدًا: لا تستخدم الخاصية القديمة `titlefont` في Plotly، واستخدم `title_font` أو `tickfont` بدلاً منها.
"""

    # قائمة النماذج المتاحة على Groq (مرتبة من الأقوى إلى الأسرع)
    models_to_try = [
        'llama-3.3-70b-versatile',
        'openai/gpt-oss-120b',
        'qwen/qwen3-32b',
        'llama-3.1-8b-instant',
    ]
    response = None
    last_error = None

    try:
        with st.spinner("🤖 جاري توليد المحاكاة..."):
            for model_name in models_to_try:
                try:
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": "أنت مساعد خبير في كتابة أكواد Python للمحاكاة الفيزيائية."},
                            {"role": "user", "content": system_prompt}
                        ],
                        temperature=0.3,
                        max_tokens=4000,
                    )
                    break  # إذا نجح الاتصال، اخرج من الحلقة
                except Exception as e:
                    last_error = e
                    continue  # جرب النموذج التالي في القائمة

        if response is None:
            st.error(f"❌ جميع النماذج مشغولة حالياً. يرجى المحاولة بعد قليل.")
            return None, None

        response_text = response.choices[0].message.content or ""

        code_match = re.search(r"```python(.*?)```", response_text, re.DOTALL)
        code = code_match.group(1) if code_match else response_text
        code = clean_code(code)

        if not code:
            st.error("⚠️ لم يتم توليد كود صالح من الذكاء الاصطناعي.")
            return None, None

        local_scope = {
            "np": np,
            "go": go,
            "px": px,
            "math": math,
            "random": random,
            "fig": None,
            "analysis_html": None,
            "__builtins__": __builtins__,
        }

        exec(code, local_scope)

        fig = local_scope.get("fig", None)
        analysis_html = local_scope.get("analysis_html") or \
            "<h3>تم تنفيذ المحاكاة بنجاح.</h3>"

        if fig is None:
            st.warning("⚠️ لم يتم إنشاء رسم بياني.")
            return None, analysis_html

        return fig, analysis_html

    except Exception as e:
        tb = traceback.format_exc()
        st.error(f"❌ حدث خطأ أثناء بناء التجربة: {str(e)}")
        with st.expander("تفاصيل الخطأ التقني"):
            st.code(tb)
        return None, None


# ==================== واجهة Streamlit ====================
st.set_page_config(
    page_title="المعمل الشامل للفيزياء بالذكاء الاصطناعي",
    page_icon="🧪",
    layout="wide",
)

st.title("🧪 المعمل الشامل للفيزياء بالذكاء الاصطناعي")
st.markdown("### أدخل اسم أي تجربة، أو ارفع كتاب الفيزياء، وسيقوم الذكاء الاصطناعي بتنفيذها فوراً!")

with st.sidebar:
    st.header("⚙️ إعدادات المعمل")
    exp_text_input = st.text_area(
        "📝 اسم التجربة / نص التجربة",
        placeholder="مثال: تجربة المقذوفات، أو قانون أوم...",
        height=150,
    )
    pdf_file_input = st.file_uploader(
        "📁 أو ارفع ملف كتاب الفيزياء (PDF)",
        type=["pdf"],
    )
    btn_run = st.button("⚡ توليد وتنفيذ التجربة فوراً", type="primary", use_container_width=True)

# منطقة العرض الرئيسية
col1, col2 = st.columns([1.5, 1])

with col1:
    st.subheader("📊 المحاكاة التفاعلية")
    plot_placeholder = st.empty()

with col2:
    st.subheader("📖 الشرح الفيزيائي والقوانين")
    html_placeholder = st.empty()

if btn_run:
    if not exp_text_input and pdf_file_input is None:
        st.warning("⚠️ يرجى كتابة اسم التجربة أو رفع ملف كتاب الفيزياء.")
    else:
        fig, analysis_html = run_universal_lab(exp_text_input, pdf_file_input)
        if fig is not None:
            plot_placeholder.plotly_chart(fig, use_container_width=True)
        if analysis_html:
            html_placeholder.markdown(analysis_html, unsafe_allow_html=True)
