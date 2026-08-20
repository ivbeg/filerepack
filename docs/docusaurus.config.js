// @ts-check
// Note: type annotations allow type checking and IDEs autocompletion

const lightCodeTheme = require('prism-react-renderer').themes.github;
const darkCodeTheme = require('prism-react-renderer').themes.dracula;

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'filerepack',
  tagline: 'Lossless-first recompression for Office, archives, images, PDFs, and data files',
  favicon: 'img/favicon.svg',

  url: 'https://ivbeg.github.io',
  baseUrl: '/filerepack/',

  organizationName: 'ivbeg',
  projectName: 'filerepack',
  deploymentBranch: 'gh-pages',
  trailingSlash: false,

  onBrokenLinks: 'throw',
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: require.resolve('./sidebars.js'),
          editUrl: 'https://github.com/ivbeg/filerepack/edit/master/docs/docs/',
          routeBasePath: '/',
        },
        blog: false,
        theme: {
          customCss: require.resolve('./src/css/custom.css'),
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      image: 'img/logo.svg',
      navbar: {
        title: 'filerepack',
        logo: {
          alt: 'filerepack logo',
          src: 'img/logo.svg',
        },
        items: [
          {
            to: '/',
            label: 'Contents',
            position: 'left',
            activeBaseRegex: '^/filerepack/?$',
          },
          {
            type: 'docSidebar',
            sidebarId: 'docs',
            position: 'left',
            label: 'Docs',
          },
          {
            to: '/getting-started/cookbook',
            label: 'Cookbook',
            position: 'left',
          },
          {
            href: 'https://ivbeg.github.io/filerepack/llms.txt',
            label: 'llms.txt',
            position: 'right',
          },
          {
            href: 'https://github.com/ivbeg/filerepack',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Docs',
            items: [
              {
                label: 'Contents',
                to: '/',
              },
              {
                label: 'Getting Started',
                to: '/getting-started/installation',
              },
              {
                label: 'CLI Reference',
                to: '/commands/',
              },
              {
                label: 'Formats',
                to: '/formats/',
              },
              {
                label: 'Cookbook',
                to: '/getting-started/cookbook',
              },
            ],
          },
          {
            title: 'For coding agents',
            items: [
              {
                label: 'llms.txt',
                href: 'https://ivbeg.github.io/filerepack/llms.txt',
              },
              {
                label: 'Python library',
                to: '/library/',
              },
              {
                label: 'CLI reference',
                to: '/commands/',
              },
              {
                label: 'External tools',
                to: '/tools/',
              },
            ],
          },
          {
            title: 'Project',
            items: [
              {
                label: 'GitHub',
                href: 'https://github.com/ivbeg/filerepack',
              },
              {
                label: 'PyPI',
                href: 'https://pypi.org/project/filerepack/',
              },
              {
                label: 'Changelog',
                href: 'https://github.com/ivbeg/filerepack/blob/master/CHANGELOG.md',
              },
              {
                label: 'License',
                to: '/license',
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} Ivan Begtin and contributors. filerepack is BSD licensed.`,
      },
      prism: {
        theme: lightCodeTheme,
        darkTheme: darkCodeTheme,
        additionalLanguages: ['python', 'bash', 'toml', 'json'],
      },
    }),
};

module.exports = config;
