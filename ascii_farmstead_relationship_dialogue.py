from __future__ import annotations

"""Contextual adult-romance and household dialogue content.

The functions here are deliberately pure.  They expand authored variety while
leaving relationship, family, and save authority with the existing game
systems that call them.
"""

import hashlib
from typing import Optional, Dict, Mapping, Sequence, Tuple


def _pick(seed: str, values: Sequence[str]) -> str:
    choices = tuple(str(value) for value in values if str(value))
    if not choices:
        return ""
    digest = hashlib.sha256(str(seed).encode("utf-8")).digest()
    return choices[int.from_bytes(digest[:8], "big") % len(choices)]


class _SafeContext(dict):
    def __missing__(self, key: str) -> str:
        return ""


def _render(template: str, context: Mapping[str, object]) -> str:
    values = _SafeContext({key: str(value) for key, value in context.items()})
    return " ".join(str(template).format_map(values).split())


ROMANCE_FLIRT_RESPONSES: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "interest": {
        "playful": (
            "You are getting confident. I have not decided whether that is charming or dangerous.",
            "That was smoother than I expected. You may try again when I am less prepared for it.",
            "If distracting me was the plan, you should know it worked.",
            "Careful. I might begin looking forward to these interruptions.",
            "You have an inconvenient talent for making ordinary conversation feel charged.",
            "I noticed you before you spoke. I was hoping you would give me a reason not to look away.",
        ),
        "admiring": (
            "You notice more than most people do. That means something to me.",
            "I am not accustomed to being looked at quite that carefully.",
            "That is a thoughtful thing to say. I will try not to let it go to my head.",
            "You make admiration sound less like praise and more like an invitation.",
            "That is dangerously close to the exact compliment I wanted from you.",
            "I like the way you notice me. It feels attentive rather than merely hungry.",
        ),
        "direct": (
            "That is direct. I respect it, even if I need a moment to decide what to do with it.",
            "You do not leave much room for misunderstanding, do you? I may like that.",
            "I wondered when you would finally say it plainly.",
            "I am interested. I simply prefer that we do not rush past actually knowing each other.",
            "The attraction is mutual. I am saying that plainly so neither of us has to pretend otherwise.",
            "Yes, I have thought about you that way. No, I am not telling you how often yet.",
        ),
        "private": (
            "That is a tempting suggestion, but I want trust to arrive before privacy does.",
            "Not yet. Ask me again when this feels less like possibility and more like us.",
            "You are bold. I am interested enough not to dismiss it, and cautious enough not to agree yet.",
            "Keep that thought. We are not quite there, but I would be lying if I said I felt nothing.",
            "Privacy with you is appealing. Trusting what happens after privacy is the part I am still considering.",
            "I have imagined saying yes. For now, knowing that will have to be enough.",
        ),
    },
    "dating": {
        "playful": (
            "You know exactly what you are doing, and I am beginning to enjoy letting you do it.",
            "If you keep looking at me like that, neither of us is finishing much work today.",
            "I was behaving perfectly well before you arrived. This is clearly your fault.",
            "Come closer and say that again. I want to see whether you can keep a straight face.",
            "You are making it very difficult to remember why I intended to behave today.",
            "Keep teasing me and I will eventually stop pretending I intend to resist.",
        ),
        "admiring": (
            "I like being seen by you, especially when you notice the parts I never advertise.",
            "That look from you still catches me off guard—in a very good way.",
            "You make me feel wanted without making me feel possessed. Keep doing that.",
            "I enjoy your attention most when it feels this deliberate and this unmistakably personal.",
            "You have learned exactly which look makes me forget the sensible answer I prepared.",
            "I could get used to hearing that from you, though I hope you never say it from habit.",
        ),
        "direct": (
            "Then stop waiting and kiss me—unless you intend to keep talking until the moment passes.",
            "Good. I have been wanting the same thing, and patience is becoming overrated.",
            "I appreciate the warning. Now I have time to decide whether to make you wait.",
            "That makes two of us. We should probably do something about it.",
            "Then come here. I would rather feel your answer than continue discussing mine.",
            "Good. I am done being subtle, and I would like you closer now.",
        ),
        "private": (
            "Later. Somewhere quiet, with no schedule demanding the better part of us.",
            "I like that idea. Give me a little time to finish here, then keep the evening for me.",
            "You have my attention. Save the rest for when we do not have an audience.",
            "All right. But when we have privacy, do not suddenly become shy on me.",
            "Meet me later and leave enough time that neither of us has to hurry back to being responsible.",
            "I want that too. Somewhere private, where I can stop editing my response for an audience.",
        ),
    },
    "engaged": {
        "playful": (
            "We are already planning a wedding and you still flirt as if you are trying to win me over. I approve.",
            "You realize I already said yes? Not that I want you to stop making the case.",
            "If this is how you behave while engaged, married life may be considerably less orderly than planned.",
            "Keep that up and I may insist we move the wedding closer.",
            "I agreed to marry you, not to become immune to you. Clearly the opposite happened.",
            "If you keep tempting me during wedding planning, the schedule is going to become very inefficient.",
        ),
        "admiring": (
            "I want you to keep looking at me that way after the ceremony, after the work, after the years.",
            "Being chosen by you feels especially good when you make it clear the choice is still alive.",
            "You make the future feel less like a plan and more like something I can hardly wait to begin.",
            "I know we are building a household. I am glad we have not forgotten the desire underneath it.",
            "I want the years with you, but I also want this anticipation—the part where one look still changes the room.",
            "You make commitment feel intimate rather than restrictive, and that makes me want you more, not less.",
        ),
        "direct": (
            "Come here, then. Being engaged is no reason to waste a perfectly good kiss.",
            "I was hoping you would say that before we got buried in another wedding decision.",
            "You still have that effect on me. I hope you understand how much I enjoy it.",
            "There is my future {player_kin}—honest, impatient, and very difficult to resist.",
            "Yes. Kiss me first, and we can return to being practical when one of us remembers how.",
            "I was hoping you would stop discussing desire as if it were a future appointment.",
        ),
        "private": (
            "Keep the evening clear. I want a little time with you that belongs to neither work nor wedding plans.",
            "That sounds much better than another conversation about guest lists. Find me when we are alone.",
            "I have been thinking the same thing. Later, shut the rest of the world outside for a while.",
            "Yes. We can be responsible tomorrow; tonight I want your attention entirely on me.",
            "Later, I want the door closed, the plans ignored, and no uncertainty about why we are alone.",
            "Keep tonight for us. I have spent enough time imagining it to know I do not want interruptions.",
        ),
    },
    "married": {
        "playful": (
            "Flirting with your own {speaker_kin}? Scandalous. You should probably do it again.",
            "You are fortunate I find that expression on your face extremely convincing.",
            "I know that tone. Whatever you are planning, I am already considering saying yes.",
            "The chores can survive a few minutes without us. Come here.",
            "I married you, which means I know exactly how persuasive you can be and still let you try.",
            "That expression usually leads to neglected chores and an excellent evening. I accept the risk.",
        ),
        "admiring": (
            "I love that you still see me as someone to desire, not merely someone who shares the work.",
            "After everything ordinary we have shared, you can still make me feel newly chosen.",
            "You know me well enough for that compliment to land exactly where you intended.",
            "I want us to keep noticing each other like this, especially when life becomes crowded.",
            "I know every ordinary version of you and still feel this pull when you look at me deliberately.",
            "Desire feels safer with someone who knows my whole life and still bothers to make me feel chosen.",
        ),
        "direct": (
            "Then kiss me. We have earned the right to be direct with each other.",
            "Good. I wanted you too, and I was becoming tired of waiting for you to notice.",
            "Come closer. I would rather answer that properly than explain it.",
            "You have my attention. Completely, inconveniently, and very willingly.",
            "Come upstairs with me. Whatever can wait downstairs is about to prove that it can.",
            "Yes. Stop asking as if I have not been wanting the same thing all evening.",
        ),
        "private": (
            "When the house is quiet, come find me. I intend to keep you to myself for a while.",
            "Lock the door when you come in. The rest of the household can manage without us for one evening.",
            "Finish what you need to finish, then meet me upstairs. Do not make me wait too long.",
            "I was hoping you would suggest that. Later, I want time that belongs only to us.",
            "When the house settles, meet me in our room. I have no intention of spending the whole night talking.",
            "Close the curtains later. I want the private version of you, and I want enough time to enjoy it.",
        ),
    },
}


ROMANCE_DEMEANOR_TAILS: Dict[str, Tuple[str, ...]] = {
    "warm": ("I like hearing you say it.", "You make it very easy to answer warmly."),
    "reserved": ("Give me a moment; I am enjoying that more than I intend to show.", "Do not mistake quiet for disinterest."),
    "skeptical": ("You may have to prove you mean it.", "I am listening, though I reserve the right to tease you about it."),
    "blunt": ("Good. I prefer honesty.", "That is much better than hinting around it."),
    "professional": ("You chose an inconveniently effective time to say that.", "I am technically working, but I heard every word."),
    "neutral": ("I will remember that.", "That landed better than you may realize."),
}


ROMANCE_STATUS_LINES: Dict[str, Tuple[str, ...]] = {
    "interest": (
        "I am interested, but I want the interest to become knowledge before either of us makes promises.{planned}",
        "There is something between us. I would rather let it become specific than rush to name it.{planned}",
        "I notice when you arrive, and I think about our conversations afterward. That is where I am.{planned}",
        "I like the direction this is taking. I also like that neither of us has to pretend certainty too early.{planned}",
        "We are {friendship_lower}, and the attraction is real. I want to see what we do with it.{planned}",
        "You have my attention. Trust is the part I still want us to earn carefully.{planned}",
    ),
    "dating": (
        "We are dating, and I want it to feel like more than a sequence of successful conversations.{planned}",
        "I am happy with us. I want more ordinary time together, not only occasions chosen to impress each other.{planned}",
        "I trust the attraction. Now I want to know how we handle tired days, disagreements, and changed plans.{planned}",
        "You are becoming part of how I imagine the next season of my life.{planned}",
        "I want this relationship, including the inconvenient parts that cannot be solved by charm.{planned}",
        "We are {friendship_lower}, affectionate, and still learning each other's edges. That feels honest.{planned}",
    ),
    "engaged": (
        "I said yes because I want the marriage, not merely the wedding. I am still very much looking forward to both.{planned}",
        "We are engaged. The plans matter, but the private life underneath them matters more to me.{planned}",
        "I am ready to build a household with you without pretending either of us stops being an individual.{planned}",
        "I love that our future is becoming concrete, and I want us to keep choosing it instead of treating it as inevitable.{planned}",
        "We have made a serious promise. I do not want seriousness to make us less playful with each other.{planned}",
        "I am excited, nervous, attracted to you, and certain enough to say all three plainly.{planned}",
    ),
    "married": (
        "You are my {player_kin}, my family, and still the person I want when the practical parts of the day are finished.{planned}",
        "I love our household, but I do not want the household to consume the marriage that created it.{planned}",
        "We know each other well enough to be honest and still have enough to learn that I remain interested.{planned}",
        "I choose this life with you in the ordinary sense: meals, worries, desire, work, and trying again after poor days.{planned}",
        "We are {friendship_lower}, but that label cannot hold everything we have built together.{planned}",
        "I want us to remain lovers as well as partners, and partners as well as the people who keep the household running.{planned}",
    ),
}


def romance_flirt_response(
    stage: str,
    style: str,
    demeanor: str,
    seed: str,
    context: Optional[Mapping[str, object]] = None,
) -> str:
    """Pick a flirt line, optionally filling kinship terms.

    ``player_kin`` is what the player is to the speaker ("wife"/"husband") and
    ``speaker_kin`` is what the speaker is to the player. Both fall back to the
    neutral "spouse" when the context omits them, so older callers still work.
    """
    stage_key = stage if stage in ROMANCE_FLIRT_RESPONSES else "interest"
    style_key = style if style in ROMANCE_FLIRT_RESPONSES[stage_key] else "playful"
    base = _pick(f"{seed}:base", ROMANCE_FLIRT_RESPONSES[stage_key][style_key])
    tails = ROMANCE_DEMEANOR_TAILS.get(demeanor, ROMANCE_DEMEANOR_TAILS["neutral"])
    tail = _pick(f"{seed}:tone", tails)
    filled = {"player_kin": "spouse", "speaker_kin": "spouse"}
    filled.update({str(k): str(v) for k, v in (context or {}).items()})
    return _render(f"{base} {tail}", filled)


def romance_status_line(
    stage: str,
    context: Mapping[str, object],
    seed: str,
) -> str:
    stage_key = stage if stage in ROMANCE_STATUS_LINES else "interest"
    template = _pick(f"{seed}:{stage_key}", ROMANCE_STATUS_LINES[stage_key])
    filled = {"player_kin": "spouse", "speaker_kin": "spouse"}
    filled.update({str(k): str(v) for k, v in (context or {}).items()})
    return _render(template, filled)


SPOUSE_HOUSEHOLD_LINES: Dict[str, Tuple[str, ...]] = {
    "plans": (
        "I am {activity}. After that, I want enough of the day left that we can actually see each other.",
        "My schedule is manageable, but I do not want us to become two people exchanging task lists at the door.",
        "I can handle today's work. Tell me where your day is taking you so I know when to expect you home.",
        "There is work to do, but the {priority_lower} priority should change what we protect time for.",
        "I planned around {activity}. If your route changes, tell me before I start worrying.",
        "Most of today is ordinary. I would like the part we share not to feel accidental.",
        "I have a full day, but not so full that there is no room for you in it.",
        "Let us compare plans now instead of discovering at midnight that each of us expected the other somewhere else.",
    ),
    "home": (
        "These days {home} feels lived in, not merely occupied. I like the traces we leave in each other's routines.",
        "A shared home is mostly ordinary negotiations. I am glad ours still contains affection between them.",
        "I want this place to hold more than our belongings. I want it to hold evenings we actually remember.",
        "The household works best when neither of us quietly becomes responsible for everything.",
        "I like coming home and knowing whose footsteps I am hearing before I turn around.",
        "We have changed this place simply by building habits inside it. That matters more than the furniture.",
        "Some days the house feels too quiet; other days I would pay for ten uninterrupted minutes. Both feel like ours.",
        "Whatever property we own, home is the place where we are allowed to stop performing competence for everyone else.",
    ),
    "needs": (
        "I need honesty before I need help. If something is wearing you down, tell me while we can still share the weight.",
        "What I need most is for us to notice strain before it becomes resentment.",
        "I could use an evening without plans, obligations, or somebody needing the capable version of me.",
        "Ask me again after I finish {activity}. I appreciate that you asked before deciding for me.",
        "I need you present when you are home—not perfect, just actually here with me.",
        "Right now I am all right. That does not make the question unnecessary; it makes it easier to answer honestly.",
        "I want support that leaves me feeling capable, not managed. You usually understand the difference.",
        "I need room to be tired without turning it into a household emergency.",
    ),
    "affection": (
        "Come sit close for a while. Nothing is wrong; I simply want you near me.",
        "I missed you today, even though I knew exactly where you were.",
        "There you are. Give me a moment before the household remembers all the things it wants from us.",
        "I love the life we are building. I also love the person I married, separately from every useful thing you do.",
        "We should be careful not to save all our tenderness for anniversaries and emergencies.",
        "Stay with me a minute. The rest of the day can wait its turn.",
        "I still notice when you enter a room. I hope I never become too accustomed to that.",
        "You look like someone who needs to be reminded they are loved without having to earn it first.",
    ),
    "children": (
        "I think {children} notice more of our habits than either of us realizes. I want them to see us repair mistakes as well as avoid them.",
        "I think {children} could use time with us that is not secretly a lesson or a chore.",
        "The children are becoming themselves in front of us. It is exciting and a little frightening to witness.",
        "I do not want us to agree on everything about the children; I want us to disagree without making them carry it.",
        "Lately {children} {children_have} been changing quickly. We should compare what each of us has noticed.",
        "I want the children to remember this home as dependable, not perfect.",
        "We should ask {children} what they want from the next family day instead of choosing it entirely for them.",
        "Raising them is a long conversation. I am glad I am having it with you.",
    ),
    "finances": (
        "We have {money}g and {property_count} outside {property_label}. I care less about the total than whether our plans agree with it.",
        "Money is useful, but I do not want every household decision reduced to what pays fastest.",
        "We can afford to plan ahead. The question is what kind of life we are actually trying to purchase.",
        "If we are saving for something, let us name it. Vague restraint becomes resentment remarkably quickly.",
        "I trust your ambition. I also want enough security that one poor season does not dictate our choices.",
        "Our property is growing, but I do not want our obligations to grow faster than our lives can hold.",
        "Let us decide what is enough before success keeps moving the line.",
        "I would rather make one deliberate investment together than discover three separate assumptions later.",
    ),
    "safety": (
        "I know why you travel. I am not asking you to become smaller; I am asking you to come back.",
        "Take danger seriously without letting it make every decision for you. That is the balance I want for us.",
        "When you leave for the wilderness, tell me the route you intend to take. Silence invents worse possibilities than truth.",
        "I trust your ability. I worry because ability does not make anyone invulnerable.",
        "Bring companions when you can, and pride only when it is useful.",
        "I do not need promises that nothing will happen. I need a plan for what you will do when something does.",
        "If the weather turns {weather_lower}, choose the route that gets you home—not the one that makes the better story.",
        "You are allowed to retreat. I would rather hear an unfinished adventure than lose you to a completed one.",
    ),
    "memory": (
        "I still think about {memory}. The details have softened, but I remember how it felt to be there with you.",
        "My mind returns to {memory} at strange times. I suppose that is how a shared life marks ordinary days.",
        "We should revisit {memory}, not to repeat it exactly but to see who we are there now.",
        "I remember {memory}. You were trying very hard not to show how much the moment meant to you.",
        "That memory belongs to both of us, but I am certain we remember different parts. I like that.",
        "Sometimes I measure our life by the distance between {memory} and where we stand now.",
        "I would not change {memory}, even the awkward parts. They make the tenderness believable.",
        "We have enough history now that a single place can contain several versions of us.",
    ),
}


# Marriages do not all sound alike. Children already speak by life stage
# (CHILD_HOUSEHOLD_LINES), but a spouse said the same things whether the wedding
# was last month or thirty years ago. These layer over SPOUSE_HOUSEHOLD_LINES:
# a subject missing from a stage falls through to the flat pool below.
SPOUSE_STAGE_LINES: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "newlywed": {
        "plans": (
            "I keep making plans that assume you will be there. It is a new habit and I like it.",
            "We have not settled into a rhythm yet. I am enjoying the part where we are still deciding.",
            "Tell me your day and I will build mine around the gaps. That still feels like a novelty.",
            "I am {activity}. Ask me in a year whether I still rearrange everything to see you.",
        ),
        "home": (
            "I keep waiting for {home} to feel like mine. It feels like ours instead, which is stranger and better.",
            "I keep finding your things where I would not have put them. I have stopped moving them back.",
            "We are still learning which drawer is whose. I am in no hurry to finish.",
            "I like that this house has not settled into what it will be. Neither have we.",
        ),
        "needs": (
            "I need you to tell me when I get something wrong. Better now than in ten years.",
            "What I need is time that is not spent proving we made the right decision.",
            "I could use an evening where neither of us is trying to impress the other.",
            "I need to stop treating every disagreement as evidence. It is only a disagreement.",
        ),
        "affection": (
            "I still get a small shock when I remember you chose this. Chose me.",
            "I have not run out of things to notice about you. That seems like a good sign.",
            "Come here. No reason. I am allowed to have no reason now.",
            "I keep catching myself smiling at nothing. It is not nothing.",
        ),
        "children": (
            "Children are a conversation we have not finished. I like that we are having it slowly.",
            "I do not know yet whether I want that. I know I want to decide it with you.",
            "Ask me about children once we have survived a full season together.",
            "If we do, I want us to be the kind of household that talks about it first.",
        ),
        "finances": (
            "We have {money}g. I am less interested in the number than in agreeing what it is for.",
            "I am not used to calling the money ours. It is taking some practice.",
            "Let us decide what we are saving toward before we decide how much.",
            "I would rather be poor and honest than comfortable and quietly resentful.",
        ),
        "safety": (
            "Tell me where you are going. Not to check on you. Because I want to know.",
            "I have started worrying about you in a way I did not before. It is inconvenient.",
            "If the weather turns, come home. The story can wait.",
            "I am not used to having someone to come back to. Give me time to learn the habit.",
        ),
        "memory": (
            "I still think about {memory}. It has not worn smooth yet.",
            "We do not have many years of stories. I am collecting them deliberately.",
            "I can already tell {memory} is one we will tell badly for decades.",
            "Everything is still a first. I am trying to pay attention while that lasts.",
        ),
    },
    "parents": {
        "plans": (
            "My day belongs to {children} until evening. After that it is ours, if we are awake.",
            "I am {activity}, then the school run, then whatever the children have invented.",
            "Tell me your plans and I will find the hour that is still free. There is always one.",
            "We plan in fifteen-minute pieces now. It works better than I expected.",
        ),
        "home": (
            "I notice {home} is louder than it was. I would not trade the noise.",
            "Every room has something small and sticky in it. Apparently this is what a home is.",
            "I like that the children will remember this house the way I remember mine.",
            "The house runs on whoever is awake. Lately that is mostly you.",
        ),
        "needs": (
            "I need twenty minutes where nobody needs the capable version of me. You included, gently.",
            "What I need is for us to notice when the other one is running out.",
            "I need us to still be a couple and not only a system for raising {children}.",
            "Some days I need help. Some days I need you not to offer it. I know that is hard.",
        ),
        "affection": (
            "We are affectionate in the gaps now. I have learned to like the gaps.",
            "You are still the person I look for when something good happens. That has not changed.",
            "I loved you before {children} existed. I would like to remember that occasionally.",
            "Kiss me while nobody is asking either of us for anything.",
        ),
        "children": (
            "{children} {children_are} the best argument we ever made together.",
            "I worry I am getting it wrong with {children}. Tell me honestly if I am.",
            "I want {children} to have arguments they survive and a table they come back to.",
            "Watching you with {children} is the part I did not know to expect.",
        ),
        "finances": (
            "{money}g, and most of it is already promised to someone small.",
            "I want {children} to inherit good habits more than a good balance.",
            "We are not poor. We are permanently three purchases behind.",
            "Let us decide together before the next big spend. I do not want to guess your answer.",
        ),
        "safety": (
            "Tell me your route. I have a list of people to worry about and you are on it.",
            "If the weather turns, come home. {children} will ask where you are.",
            "I am careful now in ways I was not before. That is what {children} did to me.",
            "Keep yourself whole. That is not sentiment, it is household logistics.",
        ),
        "memory": (
            "I think {children} will remember {memory}. That changes how much it matters.",
            "I want more days like {memory} before {children} {children_are} too old to want them.",
            "We are making the memories they will misremember affectionately. No pressure.",
            "I remember {memory}, and I noticed you noticing me. I still do that.",
        ),
    },
    "enduring": {
        "plans": (
            "My day is the same as most days. Yours is the part I am curious about.",
            "I am {activity}. We both know how this evening goes, and I like that we do.",
            "Tell me if today is different. I will rearrange things without complaining much.",
            "We stopped planning years ago and started arranging. It suits us.",
        ),
        "home": (
            "By now {home} has our shape worn into it. I would not know how to live somewhere square.",
            "I know which stair creaks and which door sticks. So do you. That is its own intimacy.",
            "This house has held a great deal. It is still standing and so are we.",
            "We changed this place by living in it. That is the only renovation that matters.",
        ),
        "needs": (
            "I need less than I used to. What I still need is to be told things directly.",
            "What I need is for you to say the hard thing before it becomes an old thing.",
            "I could use a day with nothing in it. With you in it, but nothing else.",
            "I need us to keep asking. Assuming is what goes wrong at this stage.",
        ),
        "affection": (
            "I am not going to be poetic about it. You know. You have known for years.",
            "Sit down. I like the room better when you are in it.",
            "We have said everything already. I still want to hear you say it.",
            "I chose this a long time ago and have not needed to revisit the decision.",
        ),
        "children": (
            "We never had children. Most days that is simply a fact, and some days it is more than that.",
            "People stopped asking years ago. I am not sure whether that is a kindness.",
            "We built a different kind of household. I do not think it is a lesser one.",
            "If you ever want to talk about it properly, I am here. We do not have to.",
        ),
        "finances": (
            "{money}g and {property_count} {property_label}. Neither of us is impressed by the number now.",
            "We have enough. It took a long time to be able to say that plainly.",
            "I want what we leave behind to be easy to divide and hard to argue about.",
            "Money was uneven once. I notice I no longer count before speaking.",
        ),
        "safety": (
            "Mind how you go. I have earned the right to say that without explaining.",
            "I do not worry the way I used to. I worry more precisely.",
            "If it turns bad out there, come back. Everything else keeps.",
            "You have old bones like mine. Take the flat road.",
        ),
        "memory": (
            "We have told the story of {memory} so often it has become furniture.",
            "I remember {memory} differently than you do. I stopped correcting you.",
            "Most of what I have is memory now. You are a good portion of it.",
            "We should make another one like {memory} while we still can.",
        ),
    },
    "empty_nest": {
        "plans": (
            "My day is my own again. I have not entirely worked out what to do with that.",
            "I am {activity}. Nobody is waiting on me to finish, which is new.",
            "We can decide the evening on a whim now. It took me a year to believe that.",
            "Tell me what you want to do today. There is nothing to schedule it around.",
        ),
        "home": (
            "There are too many rooms in {home} now. I am not ready to say that out loud to anyone else.",
            "I still listen for them on the stairs some mornings. Old habit.",
            "This house is quiet in a way I am learning to like rather than endure.",
            "We could change any room we wanted. I keep not doing it.",
        ),
        "needs": (
            "I need us to build something that is ours, now that the raising is done.",
            "What I need is for us not to become two people who simply share a house.",
            "I could use a reason to leave the valley for a few days. With you.",
            "I need to be more than somebody's parent again. I am out of practice.",
        ),
        "affection": (
            "We have time for each other again. I intend to use it.",
            "I am courting you again, in case that was not obvious.",
            "You were the point before they arrived. You are the point now.",
            "Come here. There is nobody to interrupt us, which is still novel.",
        ),
        "children": (
            "{children} {children_are} grown and independent now. That was the point, and it is still strange.",
            "We raised them and then they left, which is the correct ending and a hard one.",
            "I miss the noise. I would not go back. Both are true.",
            "We did most of it right. The rest they will forgive us for, probably.",
        ),
        "finances": (
            "{money}g, and for the first time none of it is promised to anyone but us.",
            "We should spend some of it before we become too sensible to enjoy it.",
            "I want what we leave behind to be easy for them to divide and hard to argue about.",
            "We stopped counting for them and started counting for us. That took adjusting.",
        ),
        "safety": (
            "Mind how you go. I have fewer people to worry about, which means more attention on you.",
            "Send word if you are held up. There is nobody else here to notice.",
            "Take the easy road. Neither of us has anything to prove out there any more.",
            "Come home whole. That is the only errand that actually matters.",
        ),
        "memory": (
            "I keep going back to the years when the house was full, {memory} among them.",
            "I remember {memory} better than I remember last week. That is the arrangement now.",
            "We should be making new memories, not only maintaining the old ones.",
            "This house is full of {memory} and a hundred others. I like walking through them.",
        ),
    },
}


def spouse_stage_group(
    years_married: object, child_count: object, dependent_children: object = None
) -> str:
    """Which phase of a marriage a line should come from.

    A household still raising someone sounds like one regardless of how long the
    couple has been married.  Once the children are grown the same couple speaks
    from an emptier house, which is not the same voice as a marriage that never
    had children.  Callers that cannot tell the difference may omit
    ``dependent_children`` and every child counts as dependent.
    """
    try:
        years = float(years_married or 0)
    except (TypeError, ValueError):
        years = 0.0
    try:
        children = int(child_count or 0)
    except (TypeError, ValueError):
        children = 0
    if dependent_children is None:
        dependents = children
    else:
        try:
            dependents = int(dependent_children or 0)
        except (TypeError, ValueError):
            dependents = children
    if dependents > 0:
        return "parents"
    if children > 0:
        return "empty_nest"
    if years < 2:
        return "newlywed"
    return "enduring"


def spouse_household_line(
    subject: str,
    context: Mapping[str, object],
    seed: str,
    stage: str = "",
) -> str:
    """A spouse speaking on one household subject.

    A known marriage stage speaks from its own pool; anything else falls back to
    the stage-neutral lines, which is also what an unmarried or unknown caller
    gets.
    """
    subject_key = subject if subject in SPOUSE_HOUSEHOLD_LINES else "home"
    pool = SPOUSE_STAGE_LINES.get(str(stage or ""), {}).get(subject_key, ())
    if not pool:
        pool = SPOUSE_HOUSEHOLD_LINES[subject_key]
    template = _pick(f"{seed}:{subject_key}", pool)
    return _render(template, context)


CHILD_HOUSEHOLD_LINES: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "baby": {
        "day": ("I answer with a solemn noise and reach for you.", "I brighten when you speak, then become fascinated by your sleeve.", "I settle against you as if this was the plan all along."),
        "home": ("I watch the familiar room and relax when I hear the household nearby.", "I turn toward every known voice in the house.", "I study the light, the furniture, and your face with equal seriousness."),
        "family": ("I respond to the familiar names with a delighted kick.", "I listen to the household voices and make a quiet answering sound.", "I reach toward the next familiar person who comes close."),
        "worry": ("I fuss until you hold me, then slowly unclench my hands.", "I bury my face against you and let the noise of the room fade.", "I cannot explain what is wrong, but I accept the comfort."),
        "wish": ("I point toward something bright and make my request with great urgency.", "I reach upward, apparently asking to see the entire world from your arms.", "I offer you a hopeful sound and wait for you to interpret it correctly."),
        "memory": ("I do not have words for memories yet, but familiar songs already calm me.", "I recognize the rhythm of a story you have told before.", "I smile at a household sound that has already become familiar."),
    },
    "toddler": {
        "day": ("I did lots today. Some of it was helping and some was very important looking.", "I found something! I put it somewhere safe. I do not remember where.", "My day was big. I need a snack before I tell the whole thing."),
        "home": ("This is my house too. I know because my things are everywhere.", "I like when everybody is home and I can hear them in the other rooms.", "Can my bed move closer to the window? I want to see morning arrive."),
        "family": ("Can everybody sit together? Even the busy people?", "I know who is family. They are the people who come back.", "Can we have a family day with no boring grown-up errands?"),
        "worry": ("I had a bad thought, but it got smaller when I told you.", "The storm is too loud. You should tell it we are sleeping.", "What if everybody goes somewhere and forgets where home is?"),
        "wish": ("I want to go somewhere I have never seen and then come home for supper.", "I want a job with a tiny tool that is really mine.", "I want to choose the story tonight, even if it is the long one."),
        "memory": ("Remember when we went out together? I remember the food part best.", "I remember you carried me when I got tired. I was only a little tired.", "Can we do the thing again where everybody laughed at the same time?"),
    },
    "young": {
        "day": ("I have three things to tell you, and you have to let me finish before deciding which one is important.", "Today was mostly good. One part was unfair, but I am still working out whether it was actually unfair.", "I tried doing it the way you showed me, then I found a way that made more sense to me."),
        "home": ("Can I change my part of the room so it looks like mine and not just a place adults put a bed?", "I like knowing which sounds mean someone is cooking, working, or coming home.", "Home is better when everybody is here, but not when everybody asks what I am doing at once."),
        "family": ("Can we plan something where I get a vote too?", "I think our family is strange in a good way. Other families are probably strange too.", "I want time with everyone that does not turn into work halfway through."),
        "worry": ("Sometimes I worry you will go somewhere dangerous and decide not to tell me because I am young.", "I made a mistake and I want help fixing it before anybody gives me a speech.", "What if I am not as good at my favorite thing as I thought I was?"),
        "wish": ("I want to learn something difficult enough that nobody calls it a children's version.", "Could I choose our next outing? I already have several excellent plans.", "I want a responsibility that matters, but not one adults only pretend matters."),
        "memory": ("I remember {memory}. I noticed things there that I did not know how to explain then.", "When I think about {memory}, I remember who walked beside me more than what we did.", "Can we make another memory like {memory}, but let me help plan it this time?"),
    },
    "child": {
        "day": ("My day was complicated. Nothing terrible happened, but several small things are competing to be the important part.", "I learned something today that made an older lesson finally make sense.", "I handled more on my own than usual. I liked it, although I would not mind if you noticed."),
        "home": ("I want some privacy without everyone assuming that means something is wrong.", "I like this home, but I want a corner that can change as I do.", "Everyone has routines here. I am trying to figure out which ones are actually mine."),
        "family": ("Could we put something on the calendar that belongs to all of us, not to the farm or somebody's work?", "I know families disagree. I just want us to explain things instead of pretending we do not.", "I like hearing stories from before I was born. It makes the family feel larger than one day."),
        "worry": ("I am worried about something, and I need you to listen before you decide how easy it is to solve.", "Sometimes everybody expects me to be good at the thing I liked first. What if I change my mind?", "I do not want danger hidden from me, but I also do not want to carry every adult worry."),
        "wish": ("I want to travel somewhere that makes the lessons feel real.", "Could I spend more time learning {focus_lower}? I think I am ready for something harder.", "I want to contribute in a way people would notice if I stopped."),
        "memory": ("I remember {memory} differently now. I think I understand why it mattered to you.", "I count {memory} as one of the times I felt included instead of merely brought along.", "We should return to {memory}. I want to see what has changed besides me."),
    },
    "teen": {
        "day": ("Today was fine, which is not the same as saying I want to summarize every minute of it.", "I had a disagreement with someone. I think I was right, but I am trying to understand why they thought they were.", "I did something difficult without asking for help. I am proud of that and slightly annoyed nobody saw it."),
        "home": ("I need this to be my home without it being my whole world.", "Please knock before assuming I am available. I promise I will still come out eventually.", "I appreciate having a place here that is mine. I also want some say in what happens to it."),
        "family": ("I still want family time. I just want plans that recognize I am not six anymore.", "I know I have been distant. Sometimes I need room before I know what I actually want to say.", "I want to hear the real family stories, including the decisions adults now pretend were obvious."),
        "worry": ("I am worried I will choose a path because everyone expects it and only realize later it was never mine.", "When you travel somewhere dangerous, I would rather know the plan than be protected by silence.", "I need advice, but I do not need my decision made for me."),
        "wish": ("I want work that tests me instead of keeping me safely useful.", "I would like to travel with you somewhere real, not just somewhere selected because it is safe for children.", "I want more time with {focus_lower}. I am past collecting beginner lessons."),
        "memory": ("I remember {memory}. I was younger, but I was not oblivious.", "I still think {memory} matters, because nobody was trying to turn it into a lesson at the time.", "When I think about {memory}, I can tell how much all of us have changed."),
    },
    "adult": {
        "day": ("My day is beginning to feel like part of a life I chose instead of training for one that starts later.", "I made a decision today without wondering what you would choose first. I think that is progress.", "Work went well. I am learning that competence feels quieter than I expected."),
        "home": ("I am building independence, but I do not want that to mean treating this home like somewhere I merely used to live.", "The household feels different now that I can contribute as an adult. I notice burdens I never saw as a child.", "I need my own direction and a place in this family. I do not think those desires contradict each other."),
        "family": ("I want our relationship to grow into something adult without pretending the years before it disappeared.", "I understand more of the choices you made now. I also understand some of the choices I would make differently.", "Whatever household I build later, I want this family to remain part of my life rather than only my history."),
        "worry": ("I worry that staying will look like fear and leaving will look like rejection. Neither is what I mean.", "I have a decision to make, and I want your perspective—not permission and not an order.", "I know enough now to understand the risks, which sometimes makes choosing harder rather than easier."),
        "wish": ("I want to put what I learned about {focus_lower} to use somewhere that expects real responsibility.", "I would like us to travel together as adults before our schedules become even harder to align.", "I want to build something of my own without acting as if I built myself alone."),
        "memory": ("I remember {memory} as one of the moments that shaped what I thought family could be.", "I value {memory} more now that I understand how much work went into making it possible.", "I would like to return to {memory} with you—not as a child being taken somewhere, but as company."),
    },
}


def child_stage_group(stage: str) -> str:
    normalized = str(stage or "Child").strip().lower()
    if normalized in {"newborn", "infant"}:
        return "baby"
    if normalized == "toddler":
        return "toddler"
    if normalized == "young child":
        return "young"
    if normalized == "child":
        return "child"
    if normalized == "teen":
        return "teen"
    return "adult"


def child_household_line(
    stage: str,
    subject: str,
    context: Mapping[str, object],
    seed: str,
) -> str:
    group = child_stage_group(stage)
    subject_key = subject if subject in CHILD_HOUSEHOLD_LINES[group] else "day"
    template = _pick(f"{seed}:{group}:{subject_key}", CHILD_HOUSEHOLD_LINES[group][subject_key])
    return _render(template, context)


__all__ = [
    "CHILD_HOUSEHOLD_LINES",
    "ROMANCE_FLIRT_RESPONSES",
    "ROMANCE_STATUS_LINES",
    "SPOUSE_HOUSEHOLD_LINES",
    "SPOUSE_STAGE_LINES",
    "child_household_line",
    "child_stage_group",
    "romance_flirt_response",
    "romance_status_line",
    "spouse_household_line",
    "spouse_stage_group",
]
