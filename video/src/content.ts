export const FPS = 30;
export const TOTAL_FRAMES = 60 * FPS;
export const APPROVED_NARRATION_TEXT = 'Fruit checks happen fast, but the record often disappears with the shift. FreshSense gives grocery teams a shared inspection record. Staff can add a photo or batch of twenty. The model covers apples, bananas, oranges, mangoes, tomatoes, and pears. Photos are not stored by default. DenseNet201 looks for visible fresh or rotten patterns. A separate gate withholds unclear or unsupported inputs. A bounded Agent checks history and reviewed guidance, creates follow-up tasks, and notifies staff. High-risk actions require manager approval. Staff confirm or correct results. Managers ask grounded questions and check the daily report. FreshSense runs on Python, TensorFlow, FastAPI, React, PostgreSQL, and Azure. Try freshsenseai.com or view the code on GitHub.';

export type Callout = {label: string; x: number; y: number; delayFrame: number};
export type SceneKind = 'title' | 'screenshot' | 'manager' | 'closing';
export type Scene = {
  id: string;
  kind: SceneKind;
  startFrame: number;
  endFrame: number;
  screenshot?: string;
  headline: string;
  narration: string;
  callouts: readonly Callout[];
};

export const SCENES: readonly Scene[] = [
  {id: 'problem', kind: 'title', startFrame: 0, endFrame: 150, headline: 'Fruit checks happen fast', narration: 'Fruit checks happen fast, but the record often disappears with the shift.', callouts: []},
  {id: 'overview', kind: 'screenshot', startFrame: 150, endFrame: 252, screenshot: 'overview.png', headline: 'One shared inspection workspace', narration: 'FreshSense gives grocery teams a shared inspection record.', callouts: [{label: 'Live inspection history', x: 73, y: 45, delayFrame: 40}]},
  {id: 'batch', kind: 'screenshot', startFrame: 252, endFrame: 585, screenshot: 'batch-inspection.png', headline: 'Inspect a batch in one step', narration: 'Staff can add a photo or batch of twenty. The model covers apples, bananas, oranges, mangoes, tomatoes, and pears. Photos are not stored by default.', callouts: [{label: 'Camera or multi-photo upload', x: 36, y: 68, delayFrame: 45}, {label: 'Up to 20 images', x: 47, y: 58, delayFrame: 100}]},
  {id: 'vision', kind: 'screenshot', startFrame: 585, endFrame: 836, screenshot: 'batch-inspection.png', headline: 'Classify, or withhold', narration: 'DenseNet201 looks for visible fresh or rotten patterns. A separate gate withholds unclear or unsupported inputs.', callouts: [{label: 'DenseNet201 result', x: 73, y: 28, delayFrame: 40}, {label: 'Uncertain inputs are withheld', x: 73, y: 52, delayFrame: 110}]},
  {id: 'agent', kind: 'screenshot', startFrame: 836, endFrame: 1119, screenshot: 'agent-activity.png', headline: 'A bounded Agent follows through', narration: 'A bounded Agent checks history and reviewed guidance, creates follow-up tasks, and notifies staff. High-risk actions require manager approval.', callouts: [{label: 'Automatic follow-up tasks', x: 44, y: 31, delayFrame: 45}, {label: 'Manager approval boundary', x: 70, y: 31, delayFrame: 115}]},
  {id: 'review', kind: 'screenshot', startFrame: 1119, endFrame: 1194, screenshot: 'review-queue.png', headline: 'People make the final call', narration: 'Staff confirm or correct results.', callouts: [{label: 'Human-observed outcome', x: 72, y: 42, delayFrame: 8}]},
  {id: 'manager', kind: 'manager', startFrame: 1194, endFrame: 1326, screenshot: 'manager-chat.png', headline: 'Grounded answers, daily evidence', narration: 'Managers ask grounded questions and check the daily report.', callouts: [{label: 'Workspace citations', x: 61, y: 56, delayFrame: 30}]},
  {id: 'cta', kind: 'closing', startFrame: 1326, endFrame: 1800, headline: 'See FreshSense working', narration: 'FreshSense runs on Python, TensorFlow, FastAPI, React, PostgreSQL, and Azure. Try freshsenseai.com or view the code on GitHub.', callouts: []},
] as const;

export const NARRATION_TEXT = SCENES.map((scene) => scene.narration).join(' ');
