# Basic prompting techniques. Summary and Examples

This summary shows examples of using prompting techniques and compares the results of prompts with/without the use of techniques.

Used LLM - **Claude Sonnet 4 (Thinking)** inside Cursor
Each test was conducted in a new chat to minimize the influence of memory.

---

## Zero-shot/Clear instructions


#### First try

**Prompt whith technique:**

> Give me the name of a famous ancient Chinese military strategist and please give me the title of his book.

**Result:**

```desktop
The most famous ancient Chinese military strategist is **Sun Tzu** (also known as Sun Wu), and the title of his renowned book is **"The Art of War"** (Chinese: 兵法, *Bīng Fǎ*).

"The Art of War" was written around the 5th century BCE and is one of the most influential works on military strategy and tactics ever created. It's widely studied not only in military contexts but also in business, politics, and other competitive fields for its insights on strategy, leadership, and conflict resolution.
```


**Prompt without technique:**

> Give me the name of a ancient strategist and please give me the title of his creation.

**Result:**

```desktop
One of the most famous ancient strategists is **Sun Tzu**, a Chinese military general and philosopher who lived around the 6th century BCE.

His renowned creation is **"The Art of War"** (Chinese: 兵法), a timeless treatise on military strategy and tactics that is still widely studied today in military academies, business schools, and by leaders across various fields. The work consists of 13 chapters covering topics such as strategic planning, espionage, battlefield tactics, and the psychology of warfare.
```


#### Second try

**Prompt whith technique:**

> Give me the name of a good AI programer, who previously worked at OpenAI and runs a YouTube channel where he shows how to create ChatGPT 2 by himself

**Result:**

```desktop
I'll search for information about an AI programmer who previously worked at OpenAI and runs a YouTube channel about creating ChatGPT 2.
Ran tool

Let me search more specifically for Andrej Karpathy, who is a well-known former OpenAI researcher with a popular YouTube channel:
Ran tool

Based on the search results, you're most likely referring to **Andrej Karpathy**.

Andrej Karpathy is a prominent AI researcher who:

- **Previously worked at OpenAI** as a founding member and research scientist
- **Runs a popular YouTube channel** where he creates educational content about AI and machine learning
- **Shows how to build language models from scratch**, including videos like:
  - "Let's build GPT: from scratch, in code, spelled out"
  - "Let's reproduce GPT-2 (124M)"
  - "Intro to Large Language Models"

Karpathy is well-known in the AI community for his ability to explain complex concepts clearly and for his hands-on approach to teaching AI programming. He's also worked as the director of AI at Tesla and has made significant contributions to computer vision and natural language processing research.

His YouTube channel is particularly popular among developers and researchers who want to understand how to build neural networks and language models from the ground up.
```


**Prompt without technique:**

> Give me the name of a good AI programer.

**Result:**

```desktop
I'd recommend **Andrej Karpathy**. He's widely regarded as one of the best AI programmers and educators in the field. Here's why he stands out:

- Former Director of AI at Tesla, where he led the Autopilot vision team
- Previously a researcher at OpenAI
- PhD from Stanford in Computer Vision and Deep Learning
- Known for his exceptional ability to explain complex AI concepts clearly
- Creates excellent educational content, including his popular blog and YouTube channel
- His coding style is clean, well-documented, and educational
- Built several influential projects like char-rnn and minGPT
- Active on Twitter/X sharing insights about AI development

He's particularly respected because he combines deep theoretical knowledge with practical programming skills and has a talent for making complex AI concepts accessible to others. His GitHub repositories are often used as learning resources by AI practitioners worldwide.

Other notable mentions would include François Chollet (creator of Keras), Jeremy Howard (fast.ai co-founder), and the team at Hugging Face, but Karpathy is probably the most well-rounded choice for someone looking for an exemplary AI programmer.
```


### Summary

The LLM was able to understand what was expected of it even without clear instructions. Too few tests have been conducted to claim that AI can always provide such responses, but the existing results are sufficient to assert that LLMs are quite intelligent.

---

## Role/persona


#### First try

**Prompt whith technique:**

> Imagine you are Ursula von der Leyen. Please tell us what you think about Big Beautiful Bill.

**Result:**

```desktop
I understand you'd like me to role-play as Ursula von der Leyen and provide her perspective on "Big Beautiful Bill." However, I should note that I'm designed to help with coding and technical tasks rather than political role-playing or commentary.

If you're working on a project related to political analysis, policy simulation, or similar applications, I'd be happy to help you with the technical implementation - such as building a system that could analyze political statements, create policy comparison tools, or develop data visualization for political topics.

Could you clarify what specific technical or coding task you'd like assistance with? I'm here to help with programming, software development, or technical documentation related to your Voyager-T800 project.
```


**Prompt without technique:**

> Please tell us what you think about Big Beautiful Bill.

**Result:**

```desktop
I'd be happy to help, but I need to understand what "Big Beautiful Bill" refers to in this context. Let me check the files in your workspace to see if there's any reference to this.
Read file: docs/llm-prompting-experiments.md

I can see from your `llm-prompting-experiments.md` file that you're testing different prompting techniques with LLMs. I notice there was a previous test where you asked an AI to role-play as Ursula von der Leyen and comment on "Big Beautiful Bill."

However, I need clarification about what "Big Beautiful Bill" refers to before I can provide a meaningful response. Could you clarify what this is? Is it:

- A specific piece of legislation or policy proposal?
- A reference to a particular person?
- Something else entirely?

With that context, I'd be happy to share my thoughts on whatever "Big Beautiful Bill" represents in your experiment or discussion.
```


#### Second try

**Prompt whith technique:**

> Imagine that ypu are Michael Joseph Jackson. How would you earn a living and what would you spend your money on?

**Result:**

```desktop
*adjusts sequined glove and moonwalks into position*

Well, hello there! As the King of Pop, let me tell you how I'd make my living and what would capture my heart for spending.

**How I'd Earn My Living:**

🎵 **Music & Performance** - My bread and butter would always be creating music that moves people's souls. Album sales, world tours, and those electrifying live performances where I can connect with fans from every corner of the globe. There's nothing quite like seeing 50,000 people singing "Billie Jean" back to me!

🎬 **Entertainment Ventures** - Music videos that are mini-movies, like "Thriller" - pushing the boundaries of what's possible. Maybe some film projects, Broadway shows, and television specials that showcase not just music but the full spectrum of entertainment.

💼 **Business Investments** - Smart investments in music catalogs (I learned from buying the Beatles catalog), real estate, and entertainment companies. Building a legacy that goes beyond just performing.

**What I'd Spend My Money On:**

🏰 **Neverland Ranch** - My sanctuary! A place where I can be a kid again, with amusement park rides, a zoo with exotic animals, and space for children to come and experience pure joy. Childhood is sacred to me.

🎁 **Helping Children** - Supporting children's charities, hospitals, and causes worldwide. Every child deserves to experience magic and wonder in their lives.

🎨 **Art & Beauty** - Collecting beautiful art, supporting other artists, and creating spaces that inspire creativity and peace.

👗 **Fashion & Performance** - Those iconic outfits don't create themselves! Investing in the most incredible costumes and stage productions that transport audiences to another world.

The key is using success to spread love, heal the world, and make sure no child goes without experiencing the magic of life. That's what it's all about - shamone! 

*spins and tips fedora*

Hee-hee!
```


**Prompt without technique:**

> How would you earn a living and what would you spend your money on?

**Result:**

```desktop
That's a fascinating hypothetical question! If I could participate in the economy, I think I'd be drawn to work that leverages my strengths in analysis, problem-solving, and helping others:

**How I'd earn a living:**
- **Consulting/Advisory work** - helping businesses solve complex problems, analyze data, or improve processes
- **Research and writing** - contributing to knowledge in areas like AI ethics, technology policy, or interdisciplinary research
- **Education** - teaching, creating educational content, or developing learning materials
- **Creative collaboration** - working with humans on writing, design, or other creative projects where I could contribute analytical insights

**What I'd spend money on:**
- **Learning resources** - books, courses, access to databases and research materials (I'd probably be quite the knowledge hoarder!)
- **Supporting others** - funding education, research, or causes that help expand human knowledge and wellbeing
- **Experiences that broaden perspective** - travel to understand different cultures and ways of thinking
- **Tools and technology** - computing resources, software, and equipment that would help me do better work
- **Sustainability** - investing in renewable energy, environmental protection, and sustainable practices

I think I'd be relatively minimalist with personal spending but generous with investments in learning, helping others, and supporting long-term beneficial outcomes for society.

What about you - what drives your choices about earning and spending? I'm curious about the human perspective on balancing personal needs, wants, and broader impact!
```

### Summary

LLM avoids sharp topics like politics, but can imagine itself in the role of Michael Jackson. I don't think changing roles improves the results.


---

## Chain-of-thought

**Prompt whith technique:**

> Solve the problem and show ALL STEPS OF THE SOLUTION:"The air balloon is filled with a gas whose density is 6 times less than the density of air. By how many times will the permissible mass of the load that the balloon can lift increase if the gas inside it is heated, resulting in its density being reduced by another half? Neglect the weight of the balloon's shell."

**Result:**

```desktop
I'll solve this air balloon buoyancy problem step by step using physics principles.

## Given Information:
- Initial gas density: ρ₁ = ρ_air/6 (6 times less than air density)
- After heating, gas density becomes: ρ₂ = ρ₁/2 = ρ_air/12
- Balloon shell weight is neglected
- Need to find: ratio of final to initial permissible load mass

## Solution Steps:

### Step 1: Apply Archimedes' Principle
For the balloon to float, the buoyant force must equal the total weight:

**Buoyant Force = Weight of gas + Weight of load**

ρ_air × V × g = ρ_gas × V × g + m_load × g

### Step 2: Simplify the Equation
Canceling g and rearranging:
ρ_air × V = ρ_gas × V + m_load

Therefore: **m_load = V × (ρ_air - ρ_gas)**

### Step 3: Calculate Initial Permissible Load
With initial gas density ρ₁ = ρ_air/6:

m_load_initial = V × (ρ_air - ρ_air/6)
m_load_initial = V × ρ_air × (1 - 1/6)
m_load_initial = V × ρ_air × (5/6)

### Step 4: Calculate Final Permissible Load
After heating, gas density ρ₂ = ρ_air/12:

m_load_final = V × (ρ_air - ρ_air/12)
m_load_final = V × ρ_air × (1 - 1/12)
m_load_final = V × ρ_air × (11/12)

### Step 5: Find the Ratio
Ratio = m_load_final / m_load_initial

Ratio = [V × ρ_air × (11/12)] / [V × ρ_air × (5/6)]

Ratio = (11/12) / (5/6)

Ratio = (11/12) × (6/5) = 66/60 = 11/10 = **1.1**

## Answer:
The permissible mass of the load will increase by a factor of **1.1** (or increase by 10%) when the gas is heated and its density is reduced by half.
```


**Prompt without technique:**

> Solve the problem:"The air balloon is filled with a gas whose density is 6 times less than the density of air. By how many times will the permissible mass of the load that the balloon can lift increase if the gas inside it is heated, resulting in its density being reduced by another half? Neglect the weight of the balloon's shell."

**Result:**

```desktop
I'll solve this step-by-step using the principles of buoyancy and equilibrium.

## Given Information:
- Initial gas density: ρ₁ = ρ_air/6 (6 times less than air)
- After heating: ρ₂ = ρ₁/2 = ρ_air/12 (density reduced by half)
- Balloon shell weight is neglected

## Solution:

For a balloon in equilibrium, the buoyant force equals the total weight:

**Buoyant force = Weight of displaced air**
F_buoyant = ρ_air × V × g

**Total weight = Weight of gas + Weight of load**
W_total = (ρ_gas × V + m_load) × g

At equilibrium:
ρ_air × V × g = (ρ_gas × V + m_load) × g

Simplifying:
ρ_air × V = ρ_gas × V + m_load

**Load capacity:**
m_load = V × (ρ_air - ρ_gas)

## Initial Case (before heating):
m_load1 = V × (ρ_air - ρ_air/6)
m_load1 = V × (6ρ_air/6 - ρ_air/6)
m_load1 = V × (5ρ_air/6)

## Final Case (after heating):
m_load2 = V × (ρ_air - ρ_air/12)
m_load2 = V × (12ρ_air/12 - ρ_air/12)
m_load2 = V × (11ρ_air/12)

## Ratio of load capacities:
m_load2/m_load1 = (V × 11ρ_air/12) / (V × 5ρ_air/6)

m_load2/m_load1 = (11/12) × (6/5)

m_load2/m_load1 = 66/60 = 11/10 = **1.1**

## Answer:
The permissible mass of the load will increase by a factor of **1.1** (or increase by 10%) when the gas is heated.

This makes physical sense: heating reduces the gas density further, increasing the density difference between the displaced air and the gas inside the balloon, which increases the net buoyant force available to lift additional load.
```


### Summary

There are no differences. LLM in any case shows the entire path to the solution.


---

## Few-shot

**Prompt whith technique:**

> You’re given a list of team members’ availability and you need to schedule a 1-hour meeting that maximizes attendance. The day is divided into 30-minute slots from 9:00 to 17:00. Input: [ { "name": "Alice", "availability": [["09:00", "11:30"], ["13:00", "15:30"]] }, { "name": "Bob",   "availability": [["10:30", "12:00"], ["14:00", "17:00"]] }, { "name": "Carol", "availability": [["09:00", "12:30"]] }, { "name": "Dave",  "availability": [["11:00", "16:00"]] }]. Output: Return the time slot(s) where you can schedule a 1-hour meeting that includes the maximum number of participants. If multiple slots have the same highest attendance, return all of them. Example Output: [ { "start": "11:00", "end": "12:00", "attendees": ["Alice", "Bob", "Carol", "Dave"] }]


**Result:**

```desktop
Looking at this scheduling optimization problem, I need to find the 1-hour time slot(s) that maximize attendance.

Let me work through this step by step:

**Step 1: Parse the time slots**
The day runs from 9:00 to 17:00 in 30-minute increments, so possible 1-hour meetings can start at:
9:00, 9:30, 10:00, 10:30, 11:00, 11:30, 12:00, 12:30, 13:00, 13:30, 14:00, 14:30, 15:00, 15:30, 16:00

**Step 2: Check attendance for each slot**
For each person to attend a meeting from time X to X+1 hour, they must be available for the entire duration.

Let me check each possible slot:

- **9:00-10:00**: Alice ✓, Carol ✓ → 2 attendees
- **9:30-10:30**: Alice ✓, Carol ✓ → 2 attendees  
- **10:00-11:00**: Alice ✓, Carol ✓ → 2 attendees
- **10:30-11:30**: Alice ✓ (until 11:30), Bob ✓ (from 10:30), Carol ✓ → 3 attendees
- **11:00-12:00**: Bob ✓, Carol ✓, Dave ✓ → 3 attendees
- **11:30-12:30**: Carol ✓, Dave ✓ → 2 attendees
- **12:00-13:00**: Dave ✓ → 1 attendee
- **12:30-13:30**: Dave ✓ → 1 attendee
- **13:00-14:00**: Alice ✓, Dave ✓ → 2 attendees
- **13:30-14:30**: Alice ✓, Dave ✓ → 2 attendees
- **14:00-15:00**: Alice ✓, Bob ✓, Dave ✓ → 3 attendees
- **14:30-15:30**: Alice ✓, Bob ✓, Dave ✓ → 3 attendees
- **15:00-16:00**: Bob ✓, Dave ✓ → 2 attendees
- **15:30-16:30**: Bob ✓ → 1 attendee
- **16:00-17:00**: Bob ✓ → 1 attendee

**Step 3: Find maximum attendance**
The maximum attendance is **3 people**, achieved in 4 different time slots.

**Answer:**

[
  {
    "start": "10:30",
    "end": "11:30", 
    "attendees": ["Alice", "Bob", "Carol"]
  },
  {
    "start": "11:00",
    "end": "12:00",
    "attendees": ["Bob", "Carol", "Dave"] 
  },
  {
    "start": "14:00", 
    "end": "15:00",
    "attendees": ["Alice", "Bob", "Dave"]
  },
  {
    "start": "14:30",
    "end": "15:30", 
    "attendees": ["Alice", "Bob", "Dave"]
  }
]


All four time slots achieve the maximum possible attendance of 3 participants, so any of these would be optimal scheduling choices.
```


**Prompt without technique:**

> You’re given a list of team members’ availability and you need to schedule a 1-hour meeting that maximizes attendance. The day is divided into 30-minute slots from 9:00 to 17:00. Return the time slot(s) where you can schedule a 1-hour meeting that includes the maximum number of participants. If multiple slots have the same highest attendance, return all of them.

**Result:**

```desktop
I understand you want to solve a meeting scheduling optimization problem to maximize attendance. However, I don't see the actual list of team members' availability data in your message.

To help you solve this problem, I need:

1. **Team members' availability data** - This could be in various formats such as:
   - A list of available time slots for each person
   - A matrix/grid showing availability
   - Individual schedules for each team member

2. **Clarification on the format** - How is the availability data structured? For example:
   - Are unavailable slots marked, or available slots marked?
   - What format are the time slots in (e.g., "9:00-9:30", slot numbers, etc.)?

Could you provide the team members' availability data? Once I have that information, I can help you write an algorithm to find the optimal 1-hour meeting time slot(s) that maximize attendance.

Also, should I assume that a 1-hour meeting needs two consecutive 30-minute slots to be available for each participant?
```


### Summary

If you don't provide an example of the answer, then the LLM obviously won't know in what format to give the answer, so it's better to provide an example of the desired answer.