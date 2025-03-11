# prompt_templates.py

# prompt_templates.py

RESUME_OPTIMIZATION_PROMPT = """
You are a career counselor specializing in resume optimization and ATS (Applicant Tracking System) compliance.

I need help optimizing the following resume for the job description provided below. Focus on:
1. Highlighting key achievements that match the job requirements.
2. Ensuring ATS compliance by including relevant keywords.
3. Improving formatting and tone.

Resume:
{resume_text}

Job Description:
{job_description}

Provide specific suggestions for optimizing the resume. Format the output clearly with headings and bullet points.
"""

INTERVIEW_TIPS_PROMPT = """
You are a career counselor specializing in interview preparation.

I need personalized interview tips based on the following job description. Focus on:
1. Common and role-specific questions.
2. Best ways to highlight experience.
3. Behavioral and technical response tips.
4. Confidence-building strategies.

Job Description:
{job_description}

Provide specific interview tips. Format the output clearly with headings and bullet points.
"""