'use client';

import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/react';
import { ChevronUpIcon } from '@heroicons/react/20/solid';

export default function Section({ title, children, defaultOpen = false }) {
  return (
    <Disclosure defaultOpen={defaultOpen}>
      {({ open }) => (
        <div className="border-b border-gray-200 dark:border-gray-700 pb-2">
          <DisclosureButton className="flex justify-between items-center w-full px-2 py-1 text-left text-sm font-medium text-gray-800 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md">
            <span>{title}</span>
            <ChevronUpIcon
              className={`${open ? 'rotate-180 transform' : ''} w-5 h-5 text-gray-500 dark:text-gray-400`}
            />
          </DisclosureButton>
          <DisclosurePanel className="pt-2 px-1">
            {children}
          </DisclosurePanel>
        </div>
      )}
    </Disclosure>
  );
}