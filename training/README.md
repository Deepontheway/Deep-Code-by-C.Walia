# DeepCode adapter training

The first release should run adapters beside their exact base model. Do not merge
unrelated model families. A LoRA can only be merged into the matching base model,
tokenizer, and architecture.

Keep separate adapters for persona tone and agent tool behavior.

Only use training material that DeepCode is allowed to retain, train on, and
redistribute. Do not use cloud-provider output as distillation data unless the
applicable provider terms expressly allow that use. Record the base model,
dataset provenance, license, and evaluation result in every release.
