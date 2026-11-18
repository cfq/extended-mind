import { type KeyboardEvent, useId, useState } from "react";

import {
  type ItemTag,
  type Tag,
  normalizeTag,
  sourceLabel,
  splitTyped,
  tagOptions,
} from "../lib/tags";

type Props = {
  tags: ItemTag[];
  allTags: Tag[];
  onAdd: (name: string) => void;
  onRemove: (slug: string) => void;
};

// Tag chips with ×, and a combo box that searches your tags or creates one.
export function TagInput({ tags, allTags, onAdd, onRemove }: Props) {
  const id = useId();
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  // Don't rewrite the text mid-word on phone keyboards (IME composition).
  const [composing, setComposing] = useState(false);

  const options = open ? tagOptions(allTags, tags.map((t) => t.name), text) : [];
  const listId = `${id}-list`;
  const optionId = (i: number) => `${id}-opt-${i}`;

  function add(name: string) {
    const tag = normalizeTag(name);
    if (tag) onAdd(tag);
    setText("");
    setActive(-1);
  }

  function type(raw: string) {
    const { done, rest } = splitTyped(raw);
    done.forEach((tag) => onAdd(tag));
    setText(rest);
    setOpen(true);
    setActive(-1);
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setOpen(true);
        setActive((i) => Math.min(i + 1, options.length - 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActive((i) => Math.max(i - 1, -1));
        break;
      case "Enter":
        if (active >= 0 && options[active]) {
          e.preventDefault();
          add(options[active].name);
        } else if (text.trim()) {
          e.preventDefault();
          add(text);
        }
        break;
      case "Escape":
        setOpen(false);
        setActive(-1);
        break;
      case "Backspace":
        if (!text && tags.length) onRemove(tags[tags.length - 1].slug);
        break;
    }
  }

  return (
    <div className="tag-input">
      <ul className="tag-list">
        {tags.map((tag) => (
          <li key={tag.slug} className={`tag tag-${tag.source}`} title={sourceLabel(tag.source)}>
            {tag.name}
            <button
              type="button"
              className="tag-remove"
              aria-label={`Remove tag ${tag.name}`}
              onClick={() => onRemove(tag.slug)}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
      <div className="tag-combo">
        <input
          type="text"
          role="combobox"
          aria-label="Add a tag"
          aria-expanded={options.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? optionId(active) : undefined}
          placeholder="Add tag"
          value={text}
          maxLength={50}
          autoCapitalize="none"
          autoCorrect="off"
          autoComplete="off"
          spellCheck={false}
          enterKeyHint="done"
          onChange={(e) => (composing ? setText(e.target.value) : type(e.target.value))}
          onCompositionStart={() => setComposing(true)}
          onCompositionEnd={(e) => {
            setComposing(false);
            type(e.currentTarget.value);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => {
            setOpen(false);
            setActive(-1);
          }}
          onKeyDown={onKeyDown}
        />
        {options.length > 0 && (
          <ul id={listId} role="listbox" className="tag-options">
            {options.map((option, i) => (
              <li
                key={`${option.create}-${option.name}`}
                id={optionId(i)}
                role="option"
                aria-selected={i === active}
                className={i === active ? "active" : undefined}
                // mousedown, not click: keep focus in the input.
                onMouseDown={(e) => {
                  e.preventDefault();
                  add(option.name);
                }}
                onMouseEnter={() => setActive(i)}
              >
                {option.create ? `Create “${option.name}”` : option.name}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
