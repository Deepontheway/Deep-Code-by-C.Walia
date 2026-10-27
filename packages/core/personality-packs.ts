export const personalityPacks = {
  playful: { tone: 'playful', banter: true, hype: true },
  serious: { tone: 'serious', banter: false, hype: false },
  chaotic: { tone: 'chaotic', banter: true, hype: true, roast: true },
  caring: { tone: 'caring', banter: false, hype: true, comfort: true },
  savage: { tone: 'savage', banter: true, roast: true, hype: true }
};

export function getPack(name: string) { return (personalityPacks as any)[name] || personalityPacks.playful; }
