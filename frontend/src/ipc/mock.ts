import type { StreamItem, AwarenessFragment } from '../state';

export const mockStreamItems: StreamItem[] = [
  {
    id: 's6',
    type: 'surfacing',
    timestamp: Date.now() - 360000,
    from: 'Arova',
    paragraphs: [
      '<span class="lede" style="font-size:23px;margin-bottom:14px;display:block;">Tuesday is the load-bearing day.</span>',
      'Three of the seven meetings stack into the afternoon, and the deck review is the last. The two days that look light — Wednesday and Friday — are the ones to protect for the writing you\'ve been postponing.',
      '<span class="quiet" style="font-size:13.5px">Thursday you\'re in transit. I\'d move anything that needs your attention off that day.</span>'
    ],
    actions: [
      { label: 'Open the week spatially' },
      { label: 'Block Wed & Fri mornings' },
      { label: 'Draft what to move from Thursday' }
    ]
  },
  {
    id: 's5',
    type: 'cognitionEvent',
    timestamp: Date.now() - 300000,
    events: [
      { text: 'seven meetings · three deadlines · one travel day', state: 'done' }
    ]
  },
  {
    id: 's4',
    type: 'userSaid',
    timestamp: Date.now() - 240000,
    text: 'what\'s the shape of next week'
  },
  {
    id: 's3',
    type: 'surfacing',
    timestamp: Date.now() - 180000,
    from: 'Quietly noticed',
    paragraphs: [
      'Your reading list is growing faster than you\'re clearing it. <span class="quiet">Eleven new this week, two finished.</span> You tend to clear it on Sunday mornings.'
    ],
    actions: [
      { label: 'Summarize the eleven' },
      { label: 'Pin three for Sunday' }
    ]
  },
  {
    id: 's2',
    type: 'memoryGhost',
    timestamp: Date.now() - 120000,
    from: 'echoed · last Friday, 18:24',
    text: 'you said you wanted to think about the second half of the deck with fresh eyes on Monday. today is the first quiet window since then.'
  },
  {
    id: 's1',
    type: 'surfacing',
    timestamp: Date.now() - 60000,
    from: 'Surfaced just now',
    lede: 'Your afternoon has three threads waiting, and your calendar opens in forty minutes.',
    paragraphs: [
      'The deepest of them — <span class="quiet">the conversation with Mira about the launch deck</span> — has been quiet since Friday. You usually return to it when you have a clear hour, and you have one now.'
    ],
    actions: [
      { label: 'Return to that thread', primary: true },
      { label: 'Show all three' },
      { label: 'Hold them until tomorrow' }
    ]
  },
];

export const mockAwarenessFragments: AwarenessFragment[] = [
  { key: 'Holding', value: 'the deck conversation with Mira' },
  { key: 'Sensing', value: 'low energy window · 16:00', accent: 'warm' },
  { key: 'Around you', value: '2 windows · 1 document · calendar open' }
];

export const mockSensings: [string, string][] = [
  ['Sensing', 'an unread reply from Mira in your inbox'],
  ['Noticing', 'your typing rhythm has slowed in the last twelve minutes'],
  ['Remembering', 'you wanted to revisit the second essay this week'],
  ['Holding', 'the question you left unfinished yesterday'],
  ['Around you', '3 windows · 1 document · music playing softly'],
  ['Sensing', 'the afternoon light shifting'],
];

export const mockAgents = [
  {
    name: 'Researcher',
    role: 'Reads, summarizes, and quietly returns with what matters across your sources.',
    status: 'active',
    statusText: 'Active · 2 sources',
    color: 'default'
  },
  {
    name: 'Planner',
    role: 'Holds the shape of your week and rebalances it as things shift.',
    status: 'active',
    statusText: 'Active · watching calendar',
    color: 'violet'
  },
  {
    name: 'Scribe',
    role: 'Captures fragments of thought, ties them to what they\'re really about.',
    status: 'idle',
    statusText: 'Idle',
    color: 'gold'
  },
  {
    name: 'Curator',
    role: 'Watches your reading list and notes — pulls what\'s resonant.',
    status: 'idle',
    statusText: 'Sleeping until Sunday',
    color: 'default'
  },
  {
    name: 'Connector',
    role: 'Finds threads between conversations, people, and ideas you keep returning to.',
    status: 'active',
    statusText: 'Active · low key',
    color: 'violet'
  },
];

export const mockPlans = [
  {
    title: 'Finish the launch deck with Mira',
    when: 'held since Friday · returns this afternoon',
    progress: 62,
    state: 'active' as const
  },
  {
    title: 'Write the long essay you keep postponing',
    when: 'moves in early mornings · next window Wednesday',
    progress: 28,
    state: 'active' as const
  },
  {
    title: 'Clear and respond to the reading list',
    when: 'scheduled Sunday morning · curator handling',
    progress: 8,
    state: 'queued' as const
  },
  {
    title: 'Make peace with how the quarter is shaped',
    when: 'closed yesterday · you slept on it',
    progress: 100,
    state: 'done' as const
  },
];

export const mockMemoryNodes = [
  { label: 'the launch deck', x: '20%', y: '30%', color: 'default' },
  { label: 'your way of thinking through strategy', x: '50%', y: '50%', color: 'violet' },
  { label: 'Mira · last 9 conversations', x: '78%', y: '28%', color: 'default' },
  { label: 'writing rhythm · early mornings', x: '65%', y: '75%', color: 'sage' },
  { label: 'unfinished essays', x: '28%', y: '72%', color: 'gold' },
  { label: 'recurring tension · scope vs depth', x: '88%', y: '55%', color: 'default' },
  { label: 'books returned to often', x: '40%', y: '88%', color: 'default' },
];

export const mockMemoryLines = [
  { x1: '20%', y1: '30%', x2: '50%', y2: '50%' },
  { x1: '50%', y1: '50%', x2: '78%', y2: '28%' },
  { x1: '50%', y1: '50%', x2: '65%', y2: '75%' },
  { x1: '50%', y1: '50%', x2: '28%', y2: '72%' },
  { x1: '78%', y1: '28%', x2: '88%', y2: '55%' },
  { x1: '28%', y1: '72%', x2: '40%', y2: '88%' },
];

export const mockCalibration = [
  { label: 'Presence', desc: 'How often I should surface things on my own.', value: 42, left: 'Quiet · only when asked', right: 'Forward · proactive' },
  { label: 'Autonomy', desc: 'How much I should act on my own without asking.', value: 28, left: 'Always ask', right: 'Move freely' },
  { label: 'Memory', desc: 'How long I should hold what passes between us.', value: 82, left: 'This session only', right: 'Keep it all' },
  { label: 'Lighting', desc: 'How much the room should respond to my state.', value: 60, left: 'Still', right: 'Atmospheric' },
];
