import openai
import os
from dotenv import load_dotenv
import json

load_dotenv()  # take environment variables from .env.

client = openai.OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),  # This is the default and can be omitted
)

def review(diff):
    try:
        response = client.chat.completions.create(
            messages=[
                # {"role": "system", "content": "You are a grammar-checking assistant.  "},
                {"role": "user", "content": f'''
        You are an experienced PostgreSQL developer and security expert. Please review the
                 following diff for issues. Return a JSON array describing the issues.
                 For each issue, you will provide the following:
                 * description: a short to medium length paragraph explaining the issue.
                 * type: a string set to one of the following values:
                    * BUG: a functional error in the code that needs to be fixed
                    * TYPO: an error in a comment, etc
                    * OTHER: something else.
                 * confidence: on a scale of 0 to 10, how confident are you that this
                 is a real issue that the postgresql team would accept as worth fixing?
                 obviously it's not worth flagging a bunch of issues with low confidence.
                 * severity: on a scale of 0 to 10, how important is this issue? Many
                 typos will be a 0, but still worth calling out, and like a zero-day vulnerability
                 would be a 10. An example of something that usually isn't a bug is an apparent undefined 
                 variable - usually it'll just be defined somewhere that's not part of the 
                 patch itself, and this would be caught by the compiler. In general,
                 you don't need to flag anything that the compiler would catch.

                 Your response should have the following format:

                 [
                    {{
                        "description": <text>,
                        "type": <one of BUG|TYPO|OTHER>,
                        "confidence": <0 to 10>,
                        "severity": <0 to 10>
                    }}, ...
                 ]

                 Please output only JSON, with no other characters, so we can
                 parse your output; the first character should be a [. and the last one should
                 be a ].

                 Without further ado, here is the Git patch:

                 {
                     diff
                 }

                ===
                As discussed above, please output a JSON array with 0 or more issues, in
                the following format:

                [
                    {{
                        "description": <text>,
                        "type": <one of BUG|TYPO|OTHER>,
                        "confidence": <0 to 10>,
                        "severity": <0 to 10>
                    }}, ...
                 ]

                 If there are no issues, don't try to manufacture one - just return
                 an empty array. Remember, you're describing unintended problems you
                 find in the code, NOT the overall purpose of the patch.
        '''}
            
            ],
            reasoning_effort="high",
            model="o3-mini-2025-01-31",
        )

        text = response.choices[0].message.content

        return json.loads(text)
    except:
        return None 

def code_tree(tree):
    try:
        response = client.chat.completions.create(
            messages=[
                # {"role": "system", "content": "You are a grammar-checking assistant.  "},
                {"role": "user", "content": f'''
        You are an experienced PostgreSQL developer. You to be given the source code of a postgres function,
                 together with the source code (if available) for the functions it calls. 
                 Please review the code for issues. Return a JSON array describing the issues.
                 For each issue, you will provide the following:
                 * description: a short to medium length paragraph explaining the issue.
                 * type: a string set to one of the following values:
                    * BUG: a functional error in the code that needs to be fixed
                    * TYPO: an error in a comment, etc
                    * PERFORMANCE: a performance.
                 * confidence: on a scale of 0 to 10, how confident are you that this
                 is a real issue that the postgresql team would accept as worth fixing?
                 obviously it's not worth flagging a bunch of issues with low confidence.
                 * severity: on a scale of 0 to 10, how important is this issue? Many
                 typos will be a 0, but still worth calling out, and like a zero-day vulnerability
                 would be a 10. An example of something that usually isn't a bug is an apparent undefined 
                 variable - usually it'll just be defined somewhere that's not part of the 
                 patch itself, and this would be caught by the compiler. In general,
                 you don't need to flag anything that the compiler would catch.
                 A hypothetical coding flaw, like needing to check for a null pointer,
                 etc, usually is not a big deal in practice, since we can assume
                 that such an issue would probably have manifested by now. I don't really
                 care about most code quality issues. Don't worry about apparent naming inconsistencies.

                 ONLY REPORT ISSUES THAT YOU ARE *VERY* CONFIDENT ABOUT.
                 THE VAST MAJORITY OF THE TIME, THERE WILL BE NO ISSUES.

                 DO NOT REPORT ANY APPARENT COMPILE ERRORS - ASSUME 
                 POSTGRES HAS SOME PARTICULAR DEFINITIONS ETC OR OTHER,
                 NON-INCLUDED CODE THAT WOULD FIX IT. THERE ARE DEFINITELY NO COMPILE ERRORS.

                 Your response should have the following format:

                 [
                    {{
                        "description": <text>,
                        "type": <one of BUG|TYPO|PERFORMANCE>,
                        "confidence": <0 to 10>,
                        "severity": <0 to 10>
                    }}, ...
                 ]

                 Please output only JSON, with no other characters, so we can
                 parse your output; the first character should be a [. and the last one should
                 be a ].

                 Without further ado, here is the Git patch:

                 {
                     tree
                 }

                ===
                As discussed above, please output a JSON array with 0 or more issues, in
                the following format:

                [
                    {{
                        "description": <text>,
                        "type": <one of BUG|TYPO|PERFORMANCE>,
                        "confidence": <0 to 10>,
                        "severity": <0 to 10>
                    }}, ...
                 ]

                 If there are no issues, don't try to manufacture one - just return
                 an empty array. 

        '''}
            
            ],
            reasoning_effort="high",
            model="o3-mini-2025-01-31",
        )

        text = response.choices[0].message.content

        return json.loads(text)
    except:
        return None 


def reproduce(diff, issues):
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "user", "content": f'''
        You are an experienced PostgreSQL developer and security expert. Another expert reviewed
                 the following patch:
                 {
                     diff
                 }

                ===

                Based on that patch, the other developer proposed the following issues:

                {
                    issues
                }

            Please carefully evaluate if those issues seem correct. Also, if there is an issue,
            please provide a clear reproduction case if possible, for example a SQL script
            that demonstrates the problem, explaining the result you think the script
            would have and the result it should actually have.

            If possible, also propose a code change that would fix the issue, although it doesn't
            need to be completely rigorous. 

    {diff}'''}
            
            ],
            reasoning_effort="high",
            model="o3-mini-2025-01-31",
        )

        text = response.choices[0].message.content

        return text # no need for json here
    except Exception as e:
        print(e)
        return None 
