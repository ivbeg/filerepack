/**
 * Creating a sidebar enables you to:
 - create an ordered group of docs
 - render a sidebar for each doc of that group
 - provide next/previous navigation
 */

// @ts-check

/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  docs: [
    {
      type: 'link',
      label: 'Contents',
      href: '/',
    },
    {
      type: 'category',
      label: 'Getting Started',
      items: [
        'getting-started/installation',
        'getting-started/quick-start',
        'getting-started/when-to-use',
        'getting-started/cookbook',
        'getting-started/basic-usage',
        'getting-started/safety',
        'getting-started/troubleshooting',
        'getting-started/best-practices',
      ],
    },
    {
      type: 'category',
      label: 'Use Cases',
      items: [
        'use-cases/office-documents',
        'use-cases/archives',
        'use-cases/images-and-media',
        'use-cases/pdfs',
        'use-cases/bulk-directories',
        'use-cases/data-files',
      ],
    },
    {
      type: 'category',
      label: 'CLI Reference',
      items: [
        'commands/index',
        'commands/shared-options',
        'commands/repack',
        'commands/bulk',
        'commands/doctor',
      ],
    },
    {
      type: 'category',
      label: 'Formats and tools',
      items: ['formats/index', 'tools/index'],
    },
    {
      type: 'category',
      label: 'Library',
      items: ['library/index'],
    },
    {
      type: 'category',
      label: 'Development',
      items: ['development/contributing'],
    },
    'license',
  ],
};

module.exports = sidebars;
