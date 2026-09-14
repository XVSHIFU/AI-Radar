import MarkdownIt from "markdown-it";

// Keep authored HTML as text; only explicit web links can navigate.
const markdown = new MarkdownIt({ html: false, breaks: true, linkify: false });
markdown.disable("image");
markdown.validateLink = (url: string) => /^https?:\/\//i.test(url);
markdown.renderer.rules.link_open = (tokens, index, options, _env, self) => {
  tokens[index].attrSet("target", "_blank");
  tokens[index].attrSet("rel", "noopener noreferrer");
  return self.renderToken(tokens, index, options);
};
export function renderMarkdown(source: string): string {
  return markdown.render(source);
}
