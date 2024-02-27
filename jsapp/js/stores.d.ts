interface PageStateModalParams {
  type: string; // one of MODAL_TYPES.NEW_FORM
  [name: string]: any;
}

// TODO: either change whole `stores.es6` to `stores.ts` or crete a type
// definition for a store you need.
export namespace stores {
  const tags: any;
  const surveyState: any;
  const assetSearch: any;
  const translations: any;
  const pageState: {
    state: {
      assetNavExpanded: boolean;
      showFixedDrawer: boolean;
      modal?: {} | false;
    };
    toggleFixedDrawer: () => void;
    showModal: (params: PageStateModalParams) => void;
    hideModal: () => void;
    switchModal: (params: PageStateModalParams) => void;
    switchToPreviousModal: () => void;
    hasPreviousModal: () => boolean;
  };
  const snapshots: any;
  const session: {
    listen: (clb: Function) => void;
    currentAccount: AccountResponse;
    isAuthStateKnown: boolean;
    isLoggedIn: boolean;
  };
  const allAssets: any;
}
