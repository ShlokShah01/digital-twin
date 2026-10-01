"""Generate a realistic demo dataset for one coherent persona ("Alex Carter").

The files below intentionally exercise every loader (md, txt, json chat logs,
json emails, csv) and give enough consistent signal that the resulting digital
twin can actually answer preference/decision questions with evidence behind
them."""

from __future__ import annotations

import json
from pathlib import Path

JOURNAL_MD = """# 2025 Journal (private)

## Jan 12
Started the year by unsubscribing from three apps I wasn't using - a video
editing tool, a cloud storage upgrade, and a meditation app. Felt good. I keep
books on subscriptions: if I don't touch it for two weeks, it goes. The only
ones that survive are the ones I use almost daily. Still keeping my coffee
roaster subscription, that's non-negotiable, and Headspace.

## Jan 27
The work laptop from 2022 finally hates me. Keyboard lag during design reviews.
Everyone at the office keeps pushing the 16-inch MBPs but I'm not sure I want
to spend that much. I read three teardown reviews before even window shopping.
If I replace it, I want it to last five years minimum. Willing to buy
refurbished directly from the manufacturer if it ships with a full warranty.
Extra RAM means I don't need to think about upgrades again - that's worth more
to me than a shinier screen.

## Feb 09
Denny from sales team wants to grab dinner next week. He always picks the loud
places. I usually suggest the Thai place on Division where I can actually hear
people. Green curry with tofu, hold the heat - I order it everywhere, it's a
reliability thing. New restaurant, same dish, never disappointed.

## Feb 21
Our quarterly review. I turned down the "lead" title again. More cross-team
meetings, more stakeholder syncs, less time actually making things. I told my
manager I'd rather be the strongest contributor than the one in the most
meetings. He wrote back that he respects it. Writing > talking has never been
a problem for me - this company has a docs culture and I thrive in it.

## Mar 05
Cycling season starts. I keep telling myself I don't need the new groupset.
My bike is 8 years old, has 19,000 km, and still runs fine after I rebuilt the
wheels myself. Buying decisions for me always come back to: will this still be
good in five years? If the answer is maybe, I wait a month. Usually the want
fades. Mostly.

## Mar 18
Flight for the Portland trip booked. Window seat, early morning departure,
single carry-on. I will never check a bag again after the one time I lost one
for three days. Coach is completely fine. I spend my travel money on one nice
meal in a local spot rather than on seat upgrades.

## Apr 02
Friend asked if I want to split a new console. No. I'd rather buy one used
console after it has been out for a year than go half on a launch unit that
sells out and has review-missing bugs. FOMO has never once paid off for me.

## Apr 15
Spending check at the end of the month, and it went: 60/20/20 this month, a
little heavy on rent. Good enough. I keep six months of runway in a boring
high-yield account and I paid off the last student loan in February with the
bonus. I do not like owing people money, or banks either.

## Apr 28
Went to two galleries this weekend instead of the beer festival everyone went
to. Zero regret. I recharge alone. A small dinner with two people I actually
care about beats a loud gathering with a hundred. I decline social invites
about half the time and I have stopped apologizing for it.

## May 11
New coffee beans arrived. Same roaster as always. I have tried maybe twelve
roasters in three years and this one wins on consistency - single origin,
light roast, delivered two days after roast date. Consistency beats novelty.
I'd rather have the same great cup every day than chase a slightly better one
that I can't rely on.

## May 26
Dentist visit done. I keep this running list of adult decisions made the hard
way: floss daily (small maintenance beats big repair), take the stairs when
you can, never buy the extended warranty, always cook more than you think at
home. I pack lunch four days out of five. Eating out is a treat, not a default.

## Jun 14
Paris work trip in September. I already told the team I'm extending my stay
three days for the museums. I collect guidebooks from the 90s and plan routes
on paper. Slow travel. Two cities, done well, instead of five cities done
frantically. I do not do "packed itineraries" - that is a certain way to come
home exhausted.

## Jun 27
Saw a headline, 'the 5 productivity apps you must have,' closed the tab. My
setup is one notes app and a paper notebook. Every tool I add costs attention,
and attention is the thing I guard most. Same reason I keep notifications off
and my phone on silent. I read fiction in paperbacks. I am fine with being a
little behind the internet.

## Jul 08
Weekly budget: meal prep on Sunday, cycle to work three times, one evening out
for board games at the shop downtown. Board game group is the only recurring
commitment I keep. It is a small, reliable, weekly thing and I look forward to
it more than anything on my calendar.

## Jul 22
Honest reflection on money decisions this year: every regret I can name came
from an impulse - an expensive jacket I wore twice, a gadget I dropped on
intro. Every purchase I made after a 30-day waiting window has earned its keep.
Rule going forward: two week wait for anything above $50 that isn't groceries
or coffee.

## Aug 05
The laptop decision is finally closed. Skipped the 16-inch. Found a
manufacturer-certified refurbished 14-inch with the full RAM and storage
upgrade and a three-year warranty, for almost half of retail. It has a USB
port that a human being actually needs. This is the whole philosophy: pay for
durability and repairability, refuse to pay for the badge, and never judge a
purchase the day you make it - judge it in year three.
"""

NOTES_TXT = """Random notes, mostly my own rules:
- Coffee: pour-over, light roast, same roaster. Never instant, never drive-through.
- Food: flexitarian. Green curry is my safe order. I will not split a check into 14 items. Cash is kind of a hassle, card is fine, but I hate surprise fees.
- People: text > call, always. Calls have no undo and no edit. A call is a meeting.
- I would rather write an email than answer a phone. Leave a voicemail and I will absolutely not call back.
- Introverted. Being alone is not loneliness.
- Buying: research first, wait 30 days on anything significant, favor used and refurbished, favor the 5-year view.
- I never buy on the first visit. I make myself leave the store once and come back if it's still in my head.
- Noise canceling feels like a luxury until you realize it is basic self defense on a plane.
- Health: cycling and walking beat the gym. Meal prep beats delivery. Sleep beats late night work. I would rather under-promise and over-deliver.
- Travel: window seat, morning flight, carry-on only, museums over nightlife, one good local meal over a chain dinner.
- Work: craft over title. Well-written docs over meetings. I do my best thinking alone and my best sharing in writing.
- Subscriptions: track them, cancel the unused, keep the daily-used.
- Politics of food: avoid chains when I can, support the corner shop, bring my own bag.
- The web: I curate aggressively. No algorithm feed. RSS and search. I would rather have a slow, hand-picked internet than a fast, addictive one.
- Fitness tech: a $40 bike computer and a paper training log beat an expensive watch that nags me.
- I distrust anything free that has a "growth team" attached to it.
- If a product has a manual, I read it. This surprises people.
- Best career advice I ever took: become the person people trust with the hard problem, and you stop needing to negotiate for title.
"""

CHATS_JSON = [
    {"name": "Alex", "text": "thinking about replacing my laptop, opinions?"},
    {"name": "Sam", "text": "just get the 16 inch MBP everyone loves it"},
    {"name": "Alex", "text": "that thing is huge and costs as much as a used car"},
    {"name": "Sam", "text": "you always overthink this stuff alex lol"},
    {"name": "Alex", "text": "I read the teardowns. soldered RAM should be illegal. I'd rather take the certified refurb with real ports and a warranty"},
    {"name": "Sam", "text": "ok fair, what about the new phone? yours is ancient"},
    {"name": "Alex", "text": "it still works. two-week wait rule. if I still want it in a month I'll check used"},
    {"name": "Sam", "text": "you and your wait rule"},
    {"name": "Alex", "text": "it's saved me from four impulse buys this year alone"},
    {"name": "Sam", "text": "dinner friday? trying that new ramen spot near the river"},
    {"name": "Alex", "text": "sure, but you know I'm ordering the most reliable thing on the menu"},
    {"name": "Sam", "text": "green curry again"},
    {"name": "Alex", "text": "ramen place, so probably miso with extra greens. close enough"},
    {"name": "Sam", "text": "do you want to come to the launch party saturday, it's going to be huge"},
    {"name": "Alex", "text": "huge is exactly the problem. I'd rather join you two for coffee before you go in"},
    {"name": "Sam", "text": "you never change"},
    {"name": "Alex", "text": "I consider that a compliment"},
]

EMAILS_JSON = [
    {
        "id": "e1",
        "subject": "Re: sprint planning format",
        "to": "design-team@loop-labs.example",
        "from": "alex.carter@loop-labs.example",
        "text": "Thanks everyone for the async input. I'd propose we keep sprint "
                "planning as a written doc that we react to by EOD, and reserve "
                "the hour only for decisions that actually need a conversation. "
                "Writing it down first usually means the meeting shrinks to ten "
                "minutes. Happy to draft it.",
    },
    {
        "id": "e2",
        "subject": "Feedback on the onboarding spec",
        "to": "eng@loop-labs.example",
        "from": "alex.carter@loop-labs.example",
        "text": "Read the spec twice and the copy draft once. The flow is tight but "
                "the empty state does a lot of explaining. My suggestion: one "
                "sentence, one action, no carousel. Users will not read three "
                "features in onboarding; they will read one. Happy to pair on the "
                "revised state.",
    },
    {
        "id": "e3",
        "subject": "Re: conference talk - your draft",
        "to": "alex.carter@loop-labs.example",
        "from": "events@loop-labs.example",
        "text": "Your abstract is a strong no for the talk offer. I tend to keep my "
                "focus on the design system and say no to on-stage commitments, "
                "but I can write the supporting blog post instead.",
    },
]

PREFERENCES_CSV = """domain,choice,reasoning,when
laptop,refurbished with full warranty vs new flagship,"I pay for durability and the warranty, not the badge",purchases over 300
phone,keep current until it breaks,"two week wait rule; still works",tech
dining,reliable dish at a new place,"reliability beats novelty; never disappointed",restaurants
cooking,homenade meal prep vs delivery,"cost, control of ingredients, and quiet routine",most weeks
social,small dinner vs large party,"I recharge alone; decline about half the invites",weekends
apps,single notes app,"every tool costs attention",productivity
subscriptions,cancel unused keep daily-used,"if not touched in two weeks it goes",monthly review
travel,window seat morning flight carry-on,"avoid checked-bag lost once; museums over nightlife",any trip
career,craft over title,"strongest contributor not the one in the most meetings",reviews
money,50/30/20 with six month buffer,"do not like owing anyone",ongoing
coffee,same roaster every time,"consistency beats novelty",daily
board games,recurring weekly group,"small reliable commitment is what I look forward to",weekly
consoles,used after a year out,"never pay launch premiums or beta bugs",entertainment
health,cycling and walking over gym,"maintenance beats repair",routine
"""


def generate(dest: str | Path) -> list[Path]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    files = [
        (dest / "journal.md", JOURNAL_MD),
        (dest / "notes.txt", NOTES_TXT),
        (dest / "chats.json", json.dumps(CHATS_JSON, indent=1)),
        (dest / "preferences.csv", PREFERENCES_CSV),
        (dest / "emails.json", json.dumps(EMAILS_JSON, indent=1)),
    ]
    written = []
    for path, content in files:
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written