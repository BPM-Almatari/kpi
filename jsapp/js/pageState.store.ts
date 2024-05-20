import Reflux from 'reflux';

interface PageStateModalParams {
  type: string; // one of MODAL_TYPES
  [name: string]: any;
}

export interface PageStateStoreState {
  assetNavExpanded?: boolean;
  showFixedDrawer?: boolean;
  modal?: PageStateModalParams | false;
}

// DEPRECATED
// This is some old weird store that is responsible for two things:
// 1. toggling mobile menu
// 2. handling modal from `bigModal.es6`
class PageStateStore extends Reflux.Store {
  state: PageStateStoreState = {
    assetNavExpanded: false,
    showFixedDrawer: false,
    modal: false,
  }

  setState(newState: PageStateStoreState) {
    Object.assign(this.state, newState);
    this.trigger(this.state);
  }

  toggleFixedDrawer() {
    const _changes: PageStateStoreState = {};
    const newval = !this.state.showFixedDrawer;
    _changes.showFixedDrawer = newval;
    Object.assign(this.state, _changes);
    this.trigger(_changes);
  }

  showModal(params: PageStateModalParams) {
    this.setState({
      modal: params
    });
  }

  hideModal() {
    this.setState({
      modal: false
    });
  }

  // use it when you have one modal opened and want to display different one
  // because just calling showModal has weird outcome
  switchModal(params: PageStateModalParams) {
    this.hideModal();
    // HACK switch to setState callback after updating to React 16+
    window.setTimeout(() => {
      this.showModal(params);
    }, 0);
  }

  switchToPreviousModal() {
    if (this.state.modal) {
      this.switchModal({
        type: this.state.modal.previousType
      });
    }
  }

  hasPreviousModal() {
    return this.state.modal && this.state.modal?.previousType;
  }
}

const pageState = new PageStateStore();

export default pageState;